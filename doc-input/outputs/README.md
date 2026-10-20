# outputs: specifications of output files

One CSV file per output that has a layout, for example `ORDEXP.DAT.csv`. The discover step links each output
to its file by name. Outputs without a file here are described inside their flow.

Columns (only `field` is required):

```csv
field,start,end,length,type,description
ORDER_NO,1,16,16,A,Order number
SHIP_METHOD,17,21,5,A,Shipping method
```

A file with several record layouts (header, detail, trailer) adds a column `record`: the code each line of
that layout starts with. Positions start again at 1 in each layout.

```csv
record,field,start,end,length,type,description
H,HDR_TYPE,1,1,1,A,Record type H
H,RUN_DATE,2,9,8,N,Run date YYYYMMDD
D,DET_TYPE,1,1,1,A,Record type D
D,ORDER_NO,2,17,16,A,Order number
T,TRL_TYPE,1,1,1,A,Record type T
T,RECORD_COUNT,2,7,6,N,Number of detail records
```

Before anything else runs, the tool checks the positions of every spec: a gap, an overlap or a length that does
not fit stops the run and names the field.

With `start` and `end`, the tool checks every position and every example length. Without them (a table or a
message), fields are documented without position checks, and the data check compares rows written one per line
with the fields in spec order separated by `|` (amounts with 2 decimals, empty when there is no value), in any
row order.
