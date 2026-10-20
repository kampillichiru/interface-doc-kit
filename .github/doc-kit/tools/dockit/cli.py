"""Command line: `python .github/doc-kit/tools/doc.py <command>` from the workspace root."""

import argparse
import sys
from pathlib import Path

from . import checks, compare, context, coverage, install, lookup, review, scan, spec
from .discovery import Discovery
from .plan import Plan
from .project import InputError, Module, Paths
from .workflow import Run


def _paths(args) -> Paths:
    workspace = Path.cwd()
    input_dir = workspace / args.input
    return Paths(workspace, input_dir, workspace / args.output, Module.load(input_dir))


def cmd_next(args) -> int:
    print(Run(_paths(args)).next().render())
    return 0


def cmd_scan(args) -> int:
    paths = _paths(args)
    inventory = scan.scan(paths)
    scan.save(inventory, paths)
    print(f"{paths.rel(paths.inventory_md)}: {len(inventory.files)} files, {len(inventory.entry_points)} entry points, "
          f"{len(inventory.sql)} SQL, {len(inventory.outputs)} outputs, {len(inventory.comparisons)} comparisons.")
    return 0


def cmd_check(args) -> int:
    """Used by the agents on their own file before they finish."""
    paths = _paths(args)
    if args.unit.lower() == "discovery":
        problems = checks.discovery_problems(paths)
    else:
        discovery = Discovery.load(paths.discovery)
        plan = Plan.load(paths) or Plan.build(discovery, paths, paths.discovery.stat().st_mtime)
        unit = plan.unit(args.unit)
        if unit is None:
            print(f"Unknown unit {args.unit}. Units: {', '.join(u.id for u in plan.units)}")
            return 2
        problems = checks.unit_problems(unit, paths, discovery)
    print("OK" if not problems else "\n".join(f"{n}. {p}" for n, p in enumerate(problems, 1)))
    return 0 if not problems else 1


def cmd_conditions(args) -> int:
    """Used by the explainer: every decision line of a flow, and whether its file covers it."""
    paths = _paths(args)
    print(coverage.report(paths, Discovery.load(paths.discovery), args.unit))
    return 0


def cmd_context(args) -> int:
    """Used by the explainer and the verifier: only what one unit needs, instead of the whole inventory."""
    paths = _paths(args)
    discovery = Discovery.load(paths.discovery)
    plan = Plan.load(paths) or Plan.build(discovery, paths, paths.discovery.stat().st_mtime)
    print(context.report(paths, discovery, plan, args.unit))
    return 0


def cmd_status(args) -> int:
    paths = _paths(args)
    plan = Plan.load(paths)
    if not plan:
        print("No plan yet. Run: doc.py next")
        return 0
    print(f"{'Unit':8} {'Kind':7} {'Second check':13} {'Attempts':8} Title")
    for unit in plan.units:
        state = "SME" if unit.id in plan.stuck else (checks.verdict(paths, unit.id) or "-")
        if unit.kind == "review":
            result = review.read(paths.unit_file(unit.id))
            state = (result.verdict or "-") if result else "-"
        print(f"{unit.id:8} {unit.kind:7} {state:13} {plan.attempts.get(unit.id, 0):<8} {unit.title}")
    return 0


def cmd_retry(args) -> int:
    """A person gives a unit that ran out of attempts a new start (after answering its questions)."""
    paths = _paths(args)
    plan = Plan.load(paths)
    if not plan or not plan.unit(args.unit):
        print(f"Unknown unit {args.unit}.")
        return 2
    plan.stuck.pop(args.unit, None)
    plan.attempts[args.unit] = 0
    plan.save(paths)
    print(f"{args.unit}: attempts reset. Run /doc-run again.")
    return 0


def cmd_compare(args) -> int:
    paths = _paths(args)
    item = next((o for o in Discovery.load(paths.discovery).outputs if o.id == args.output_id and o.spec), None)
    if item is None:
        print(f"{args.output_id} is not an output with a specification in discovery.md")
        return 2
    fields = spec.load(paths.input / item.spec)
    result = compare.compare(fields, paths.test_file(item.id, "expected"), paths.test_file(item.id, "actual"))
    paths.data_report(item.id).parent.mkdir(parents=True, exist_ok=True)
    paths.data_report(item.id).write_text(compare.report(item.id, item.title, result, fields), encoding="utf-8")
    print(f"{paths.rel(paths.data_report(item.id))}: {'MATCH' if result.matches else 'DIFFERENCES'}")
    return 0 if result.matches else 1


def cmd_lookup(args) -> int:
    paths = _paths(args)
    if not paths.guide.exists() or not paths.reference.exists():
        print(f"STOP: there is no document yet ({paths.rel(paths.guide)}). Run /doc-run first.")
        return 2
    guide = paths.guide.read_text(encoding="utf-8")
    print(f"Documents: {paths.rel(paths.guide)}, {paths.rel(paths.reference)}\nStatus: {lookup.status(guide)}\n")
    found = False
    for path in (paths.guide, paths.reference):  # the business wording first, then the evidence
        text = path.read_text(encoding="utf-8")
        if lookup.find(text, args.terms):
            found = True
            print(f"## From {paths.rel(path)} (line numbers are in this file)\n")
            print(lookup.answer_material(text, args.terms) + "\n")
    if not found:
        print(lookup.answer_material("", args.terms))
    return 0


def cmd_install(args) -> int:
    """Run from the kit's own folder: puts this standard kit into a project, or brings it up to date."""
    target = Path(args.project)
    problem = install.check_target(target)
    if problem:
        print(f"STOP: {problem}")
        return 2
    changes = install.plan(target)
    if changes.standard and not changes.inputs:
        print(f"{target}: already on the standard kit.")
        return 0
    counts = ", ".join(f"{n} to {k}" for k, n in install.summary(changes).items() if n)
    if args.check:
        print(f"{target}: NOT on the standard kit ({counts}).")
        print("\n".join(changes.lines()))
        return 1
    backup = install.install(target, changes)
    print(f"{target}: installed the standard kit ({counts}).")
    if backup.exists():
        print(f"Replaced and removed files are backed up in {backup}.")
    if changes.updated or changes.removed:
        print("The kit changed: run /doc-run again. If units fail on the new checks, it sends them back to fix.")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="doc.py", description="Documentation kit tools.")
    parser.add_argument("--input", default="doc-input", help="input folder (default doc-input)")
    parser.add_argument("--output", default="doc-output", help="output folder (default doc-output)")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("next", help="decide and print the next step of the run").set_defaults(run=cmd_next)
    sub.add_parser("scan", help="write the inventory of the source").set_defaults(run=cmd_scan)
    check = sub.add_parser("check", help="check a unit file (F01, O01, O01-P2) or 'discovery'")
    check.add_argument("unit")
    check.set_defaults(run=cmd_check)
    cond = sub.add_parser("conditions", help="every decision line in the code a flow reaches, and whether the flow "
                                             "file covers it")
    cond.add_argument("unit")
    cond.set_defaults(run=cmd_conditions)
    ctx = sub.add_parser("context", help="what one unit needs (F01, O01-P2): its code, SQL, decision lines, fields "
                                         "and rules, instead of the whole inventory")
    ctx.add_argument("unit")
    ctx.set_defaults(run=cmd_context)
    sub.add_parser("status", help="show the state of every unit").set_defaults(run=cmd_status)
    retry = sub.add_parser("retry", help="(for a person) give a unit that ran out of attempts a new start")
    retry.add_argument("unit")
    retry.set_defaults(run=cmd_retry)
    look = sub.add_parser("lookup", help="(skill ask-the-docs) print the parts of the finished document that answer "
                                         "a question: ids (F01-BR05, O02-09, C01-I3), field names or words")
    look.add_argument("terms", nargs="+")
    look.set_defaults(run=cmd_lookup)
    comp = sub.add_parser("compare", help="data check: compare expected and actual for an output")
    comp.add_argument("output_id")
    comp.set_defaults(run=cmd_compare)
    inst = sub.add_parser("install", help="run from the kit's folder: install this kit into a project or update "
                                          "it (backs up what it replaces; never touches the input or output folder)")
    inst.add_argument("project", help="the project folder (its root, where .github/ goes)")
    inst.add_argument("--check", action="store_true", help="only show what would change; exit 1 if not standard")
    inst.set_defaults(run=cmd_install)
    args = parser.parse_args(argv)
    try:
        return args.run(args)
    except InputError as error:
        print(f"STOP: {error}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
