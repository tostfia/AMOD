#----------------------------------------
# Uncapacitated Facility Location Problem 
# file UFL2.mod
#---------------------------------------- 
param p >= 0 integer; # number of potential facilities
param r >= 0 integer; # number of clients

set S:=1..p; # potential facility location
set D:=1..r; # clients

param setup {u in S};
param allocation {u in S, v in D};

#var x {u in S} binary; # x[u]=1 IFF facility is activated in u
#var y {u in S, v in D} binary; # y[u,v]=1 IFF client v is served by facility u

# LINEAR RELAXATION
var x {u in S} >=0, <= 1; # x[u]=1 IFF facility is activated in u
var y {u in S, v in D}  >=0, <= 1; # y[u,v]=1 IFF client v is served by facility u


minimize TotalCost:
    sum{u in S} setup[u]*x[u]+ sum{u in S, v in D} allocation[u,v]*y[u,v];

s.t. DemandSat {v in D}: sum{u in S} y[u,v] = 1;
s.t. ConsistencyS {u in S, v in D}: y[u,v] <= x[u]; # strong formulation
#s.t. ConsistencyW {u in S}: sum{v in D} y[u,v] <= card(D)*x[u]; # weak formulation
