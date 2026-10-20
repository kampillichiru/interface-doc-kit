# business: any business context you have

Write your context at the end of this file, below the marked line, or drop files next to it as they are: `.md`,
`.txt` or `.csv`. File names do not matter. Every agent reads all of them. The more the team says here, the fewer
questions come back, and the easier the document is for someone new to the business.

Most useful, in this order:

1. **Codes and terms with their meaning**: order statuses, payment methods, shipping methods, customer tiers, and
   the business words people use. A table with the columns `Code` (or `Term`) and `Meaning` is best: the tool
   copies those meanings into the glossary of the document and checks that every code the document uses has one.
   Add a note when something is doubtful ("requires validation").
2. **The business process in plain words**, from start to end, with one example with real numbers for each case
   (for example "a return of 1 of 3 items of 500 each gives back 500 plus its tax of 90; the shipping charge of
   50 is kept"). The first example becomes the main example of the business summary.
3. **Who uses it**: customers, teams, receiving systems, schedules.
4. **Volumes**: how often each case happens (one `GROUP BY` count on the test database). A case that never
   happens is a question, not something to document in detail.
5. Anything else: old specifications, emails, meeting notes. Mark what is outdated.

The documentation copies business explanations from these files. It never writes its own.

<!-- Write your business context below this line. -->
