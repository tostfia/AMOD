import os
import json
from pathlib import Path
import glob
from facilityLocation import FacilityLocationModel

def parse_ufl_instance(filename):
    """
    Parser migliorato per problemi UFL con supporto a più formati.
    Ignora capacità e supporta sia il formato 'capacity cost' sia altri.
    """

    with open(filename, 'r') as file:
        lines = [line.strip() for line in file if line.strip()]

    m, n = map(int, lines[0].split())
    idx = 1

    fixed_costs = []
    # Determina se il file ha la forma "capacity fixed_cost" o solo "fixed_cost"
    test_line = lines[idx]
    if test_line.lower().startswith("capacity") or len(test_line.split()) == 2:
        # formato "capacity fixed_cost" o con etichetta "capacity"
        for _ in range(m):
            parts = lines[idx].split()
            try:
                cost = float(parts[-1])  # fissa all'ultimo valore
                fixed_costs.append(cost)
            except:
                raise ValueError(f"Errore nel parsing della riga: {lines[idx]}")
            idx += 1
    else:
        # Solo costi fissi (una riga ciascuno)
        for _ in range(m):
            fixed_costs.append(float(lines[idx]))
            idx += 1

    assignment_costs = []
    while len(assignment_costs) < n and idx < len(lines):
        # Ignora eventuali righe che contengono solo un numero (es. "89")
        try:
            maybe_count = int(lines[idx])
            idx += 1
        except ValueError:
            pass

        row_costs = []
        while len(row_costs) < m:
            row_costs.extend(map(float, lines[idx].split()))
            idx += 1
        assignment_costs.append(row_costs)

    assert len(assignment_costs) == n, f"Errore: letti solo {len(assignment_costs)} clienti su {n}"

    return {
        "num_facilities": m,
        "num_customers": n,
        "fixed_costs": fixed_costs,
        "assignment_costs": assignment_costs,
    }
def parse_ufl_to_model(filename):
    """Parser che restituisce direttamente un FacilityLocationModel"""

    data = parse_ufl_instance(filename)
    return FacilityLocationModel.from_dict(data)