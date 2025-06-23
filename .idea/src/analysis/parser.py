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

    lines = [line.strip() for line in lines if line.strip()]

    print(f"Debug: file {filename} ha {len(lines)} righe")
    print(f"Debug: prima riga: {lines[0]}")

    # Prima riga: numero magazzini e clienti
    m, n = map(int, lines[0].split())
    print(f"Debug: {m} magazzini, {n} clienti")

    # Estrai costi fissi (ignora capacità)
    fixed_costs = []
    for i in range(1, m + 1):
        parts = lines[i].split()
        print(f"Debug: riga magazzino {i}: {parts}")
        fixed_cost = float(parts[1])
        fixed_costs.append(fixed_cost)

    # Estrai matrice costi di trasporto
    transport_costs = []
    line_idx = m + 1

    print(f"Debug: iniziando parsing clienti dalla riga {line_idx}")

    for customer in range(n):
        print(f"Debug: processando cliente {customer}, riga {line_idx}")

        if line_idx >= len(lines):
            raise ValueError(f"File troppo corto: finito alla riga {line_idx}")

        # Salta la domanda del cliente (prima riga del blocco cliente)
        demand_line = lines[line_idx].split()
        print(f"Debug: riga domanda cliente {customer}: {demand_line}")
        line_idx += 1

        # Raccogli tutti i costi per questo cliente
        customer_costs = []

        # Verifica se i costi sono sulla stessa riga della domanda o su righe separate
        if len(demand_line) > 1:
            # Caso 1: domanda e costi sulla stessa riga
            demand = float(demand_line[0])
            customer_costs = [float(cost) for cost in demand_line[1:]]
        else:
            # Caso 2: domanda su una riga, costi su righe successive
            demand = float(demand_line[0])

            # Raccogli i costi dalle righe successive
            while len(customer_costs) < m and line_idx < len(lines):
                costs_line = lines[line_idx].split()
                print(f"Debug: riga costi {line_idx}: {costs_line}")

                for cost_str in costs_line:
                    if len(customer_costs) < m:
                        customer_costs.append(float(cost_str))
                    else:
                        break

                line_idx += 1

        print(f"Debug: cliente {customer} - raccolti {len(customer_costs)} costi: {customer_costs[:5]}...")

        # Verifica che abbiamo il numero corretto di costi
        if len(customer_costs) != m:
            raise ValueError(f"Cliente {customer}: attesi {m} costi, trovati {len(customer_costs)}")

        transport_costs.append(customer_costs)

    return {
        'filename': os.path.basename(filename),
        'n_warehouses': m,
        'n_customers': n,
        'fixed_costs': fixed_costs,
        'transport_costs': transport_costs
    }


def find_data_directory():
    """Trova la directory 'data' partendo dalla directory corrente"""
    current_dir = Path(__file__).parent

    # Cerca la directory 'data' nei livelli superiori
    for level in range(5):  # Cerca fino a 5 livelli superiori
        data_dir = current_dir / ('../' * level) / 'data'
        if data_dir.exists():
            return str(data_dir.resolve())

    return None


def process_all_files(data_dir, output_dir):
    """Processa tutti i file nella directory delle istanze"""
    instances_dir = os.path.join(data_dir, "instances", "or-library")

    if not os.path.exists(instances_dir):
        print(f"Directory delle istanze non trovata: {instances_dir}")
        return {}

    all_data = {}

    # Trova tutti i file .txt nella directory
    pattern = os.path.join(instances_dir, "*.txt")
    files = glob.glob(pattern)

    print(f"Trovati {len(files)} file nella directory {instances_dir}")

    for filepath in files:
        filename = os.path.basename(filepath)
        try:
            print(f"Parsing {filename}...")
            instance_data = parse_ufl_instance(filepath)
            all_data[filename] = instance_data
        except Exception as e:
            print(f"Errore nel parsing di {filename}: {str(e)}")
            continue

    return all_data