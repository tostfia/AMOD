from utility.facilityLocation import FacilityLocationModel


def parse_ufl_instance(filename):
    with open(filename, 'r') as file:
        lines = [line.strip() for line in file if line.strip()]

    m, n = map(int, lines[0].split())
    idx = 1

    fixed_costs = []
    test_line = lines[idx]
    if test_line.lower().startswith("capacity") or len(test_line.split()) == 2:
        for _ in range(m):
            if idx >= len(lines):
                raise ValueError("File terminato prematuramente durante lettura fixed_costs")
            parts = lines[idx].split()
            try:
                fixed_costs.append(float(parts[-1]))
            except Exception:
                raise ValueError(f"Errore parsing fixed_costs alla riga {idx+1}: {lines[idx]}")
            idx += 1
    else:
        for _ in range(m):
            if idx >= len(lines):
                raise ValueError("File terminato prematuramente durante lettura fixed_costs")
            try:
                fixed_costs.append(float(lines[idx]))
            except Exception as e:
                raise ValueError(f"Errore parsing fixed_costs alla riga {idx+1}: {lines[idx]}")
            idx += 1

    assignment_costs = []
    while len(assignment_costs) < n:
        if idx >= len(lines):
            raise ValueError(f"File terminato prematuramente durante lettura assignment_costs, letti {len(assignment_costs)} su {n}")

        # Prova a saltare una riga singola con solo un numero (es: "89")
        try:
            maybe_count = int(lines[idx])
            idx += 1
            continue
        except ValueError:
            pass

        row_costs = []
        while len(row_costs) < m:
            if idx >= len(lines):
                raise ValueError(f"File terminato prematuramente durante costruzione riga costi cliente {len(assignment_costs)+1}")
            try:
                row_costs.extend(map(float, lines[idx].split()))
            except Exception as e:
                raise ValueError(f"Errore parsing righe di assignment_costs alla riga {idx+1}: {lines[idx]}")
            idx += 1
        assignment_costs.append(row_costs)

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

