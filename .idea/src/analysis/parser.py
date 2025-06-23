import os
import json
from pathlib import Path
import glob


def parse_ufl_instance(filename):
    """
    Parser migliorato per dati UFL che gestisce diversi formati.
    """

    with open(filename, 'r') as file:
        lines = file.readlines()

    # Prima riga: numero di magazzini e clienti
    m, n = map(int, lines[0].split())
    idx = 1


    print(f"Debug: {m} magazzini, {n} clienti")

    # Estrai costi fissi (ignora capacità)
    fixed_costs = []
    for _ in range(m):
        _, fixed_cost = map(float, lines[idx].split())
        fixed_costs.append(fixed_cost)
        idx += 1

    # Matrice dei costi di assegnamento [n x m]
    assignment_costs = []
    for _ in range(n):
        idx += 1  # ignora la riga con la domanda
        costs = []
        while len(costs) < m:
            costs += list(map(float, lines[idx].split()))
            idx += 1
        assignment_costs.append(costs)
    print("num_facilities:", m, "num_customers:", n," fixed_costs:", fixed_costs, "assignment_costs:", assignment_costs)

    return {
        "num_facilities": m,
        "num_customers": n,
        "fixed_costs": fixed_costs,
        "assignment_costs": assignment_costs,
    }








