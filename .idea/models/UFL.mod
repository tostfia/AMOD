#----------------------------------------
# Uncapacitated Facility Location Problem 
# file UFL.mod
#---------------------------------------- 


param I integer >0; # numero di facility
param C integer >0; # numero di clienti

param setup_cost {j in 1..I};
param allocation_cost {i in 1..C,j in 1..I};

var x {j in 1..I} binary;
var y {i in 1..C,j in 1..I} binary;

minimize costi_totali:sum{j in 1..I} setup_cost[j]*x[j]+
		      sum{i in 1..C, j in 1..I} allocation_cost[i,j]*y[i,j];

s.t. service_constr {i in 1..C}: sum{j in 1..I} y[i,j]=1;
s.t. setup_constr {i in 1..C,j in 1..I}: y[i,j]-x[j]<=0;
