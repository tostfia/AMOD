
from config import *
import random
from configparser import ConfigParser
from datetime import datetime






def get_seed():
    """Genera un seed basato sul tempo corrente."""
    return int(datetime.now().timestamp() * 1000) % 1_000_000


def generate_ufl_instance(instance_num: int, num_facilities: int, num_customers: int, cluster_type: str):
    """
    Genera una singola istanza UFL e la salva su file.

    Arguments:
        instance_num: Numero progressivo dell'istanza nel cluster.
        num_facilities: Numero di facility (p).
        num_customers: Numero di clienti (r).
        cluster_type: Nome del cluster (es. 'SMALL_UFL').
    """
    random.seed(get_seed())

    # Leggi i range dei costi dal file di configurazione
    config = ConfigParser()
    config.read('config.ini')

    min_fixed_cost = int(config[cluster_type]['MIN_FIXED_COST'])
    max_fixed_cost = int(config[cluster_type]['MAX_FIXED_COST'])
    min_assign_cost = int(config[cluster_type]['MIN_ASSIGN_COST'])
    max_assign_cost = int(config[cluster_type]['MAX_ASSIGN_COST'])

    # Definisci il percorso e crea la directory se non esiste
    path_name = DATA_DIR / cluster_type
    path_name.mkdir(parents=True, exist_ok=True)

    instance_name = f"inst_{cluster_type}_{instance_num}.txt"
    filepath = path_name / instance_name

    # Genera i dati del problema UFL
    # 1. Costi fissi per aprire ogni facility
    fixed_costs = [random.randint(min_fixed_cost, max_fixed_cost) for _ in range(num_facilities)]

    # 2. Matrice dei costi di assegnazione (cliente -> facility)
    assignment_costs = []
    for _ in range(num_customers):
        customer_costs = [random.randint(min_assign_cost, max_assign_cost) for _ in range(num_facilities)]
        assignment_costs.append(customer_costs)

    # Scrivi l'istanza nel formato standard UFL
    with open(filepath, "w") as f:
        # Prima riga: num_facilities num_customers
        f.write(f"{num_facilities} {num_customers}\n")

        # Scrivi i costi fissi
        for cost in fixed_costs:
            f.write(f"{cost}\n")

        # Scrivi i costi di assegnazione
        for customer_row in assignment_costs:
            f.write(" ".join(map(str, customer_row)) + "\n")

    print(f"  -> Generata istanza: {instance_name}")
    return filepath.stem # Restituisce il nome del file senza estensione


def generate_cluster_of_ufl_instances(num_instances: int, f_range: list, c_range: list, cluster_type: str):
    """
    Genera un cluster di istanze UFL con parametri variabili.

    Arguments:
        num_instances: Numero di istanze da generare.
        f_range: Range [min, max] per il numero di facility.
        c_range: Range [min, max] per il numero di clienti.
        cluster_type: Nome del cluster.
    """
    print(f"\tGenerazione di {num_instances} istanze per il cluster '{cluster_type}'...")

    generated_files = []
    for i in range(num_instances):
        # Scegli un numero casuale di facility e clienti all'interno dei range specificati
        num_facilities = random.randint(f_range[0], f_range[1])
        num_customers = random.randint(c_range[0], c_range[1])

        file_stem = generate_ufl_instance(i, num_facilities, num_customers, cluster_type)
        generated_files.append(file_stem)

    print("\t...Cluster generato.")
    return generated_files


def generate_all_ufl_from_config(config_file='config.ini'):
    """
    Funzione principale che legge il file di configurazione
    e genera tutti i cluster di istanze UFL definiti.
    """
    config = ConfigParser()
    config.read(config_file)

    if not config.sections():
        print(f"Errore: Il file di configurazione '{config_file}' è vuoto o non trovato.")
        return

    for cluster in config.sections():
        print(f"\n--- Elaborazione Cluster: {cluster} ---")
        try:
            # Leggi i parametri specifici per i problemi UFL
            f_range = [int(config[cluster]['MIN_FACILITIES']), int(config[cluster]['MAX_FACILITIES'])]
            c_range = [int(config[cluster]['MIN_CUSTOMERS']), int(config[cluster]['MAX_CUSTOMERS'])]
            num_instances = int(config[cluster]['NUM_INSTANCES'])

            generate_cluster_of_ufl_instances(num_instances, f_range, c_range, cluster)

        except KeyError as e:
            print(f"Errore: Chiave mancante nel file di configurazione per il cluster '{cluster}': {e}")
        except ValueError as e:
            print(f"Errore: Valore non valido nel file di configurazione per il cluster '{cluster}': {e}")



def get_statistics(name,n_var, n_constraints, optimal_sol, sol, sol_type, status, ncuts, elapsed_time, iterations):
    gap=0
    rel_gap=0
    if optimal_sol is not None:
        gap = modulus(sol,optimal_sol)
        if abs(optimal_sol)>1e-9:
            rel_gap = gap / (abs(optimal_sol)+1e-10)
    stats={
        'instance_name': name,
        'n_vars': n_var,
        'n_constraints': n_constraints,
        'optimal_ilp': optimal_sol,
        'lp_solution': sol,
        'is_integer': sol_type,
        'status': status,
        'n_cuts': ncuts,
        'elapsed_time': round(elapsed_time),
        'gap': gap,
        'relative_gap': rel_gap,
        'iterations': iterations
    }
    return stats


def modulus(x, y):
    return abs(x - y)


