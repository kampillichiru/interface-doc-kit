# Module

Fill in the Value column. Name, Business domain and Source folders are required.

| Key | Value |
|---|---|
| Name | |
| Business domain | |
| Purpose | |
| Source folders | |
| Data check | no |
| Test database | |

- **Name**: short, no spaces; becomes the folder `doc-output/<Name>` and the document title.
- **Business domain**: for example Order management, Payments, Inventory. Never guessed from the code.
- **Purpose**: one or two sentences from the business team. Leave empty if nobody knows yet.
- **Source folders**: folders with the code, relative to the workspace root, separated by commas
  (Java, SQL, SQL in XML, configuration).
- **Data check**: `yes` when you can run SQL on a test database and get a real output file of the same run
  (see `test-data/README.md`). It is the strongest proof that the documentation is right.
- **Test database**: the SQL dialect the check SQL is written in (Oracle, SQLite, ...). Oracle when empty.
