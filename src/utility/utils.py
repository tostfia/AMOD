from datetime import datetime
import random
from pathlib import Path
from utility.facilityLocation import FacilityLocationModel
from config import *
import numpy as np
from typing import Tuple

"""Metodi per generare randomicamente istanze di UFL"""


def getSeed():
    return int(datetime.now().timestamp()) % 1_000_000


def generateInstance(instance_num: int, num_facilities: int, num_customers: int):
    random.seed(getSeed())

    base_path = DATA_DIR / "instances" / "random"
    base_path.mkdir(parents=True, exist_ok=True)

    filename = base_path / f"{instance_num}.txt"
    with open(filename, "w") as f:
        f.write(f"{num_facilities} {num_customers}\n")
        fixed_costs = [random.randint(1, 100) for _ in range(num_facilities)]
        for cost in fixed_costs:
            f.write(f"{cost}\n")

        assignment_costs_matrix = []
        for _ in range(num_customers):
            costs = [random.randint(1, 100) for _ in range(num_facilities)]
            assignment_costs_matrix.append(costs)
            f.write(" ".join(map(str, costs)) + "\n")

    model = FacilityLocationModel(num_facilities, num_customers, fixed_costs, assignment_costs_matrix)
    return model


def create_ufl_matrix(n_facilities: int, n_customers: int, assignment_costs: np.ndarray, fixed_costs: np.ndarray) -> \
Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Crea le matrici A, b, c per un problema UFL

    Args:
        n_facilities: numero di facilities
        n_customers: numero di clienti
        assignment_costs: matrice (n_customers, n_facilities) dei costi di assegnamento
        fixed_costs: array (n_facilities) dei costi fissi di apertura

    Returns:
        A: matrice dei vincoli
        b: vettore termini noti
        c: vettore costi obiettivo
    """
    assignment_costs = np.array(assignment_costs)

    # Numero totale di variabili
    n_assignment_vars = n_customers * n_facilities  # variabili x_ij
    n_facility_vars = n_facilities  # variabili y_j
    n_total_vars = n_assignment_vars + n_facility_vars

    # === MATRICE A ===

    # 1. Vincoli di assegnamento: ogni cliente deve essere servito da una facility
    # Σ_j x_ij = 1 per ogni cliente i
    A_assignment = np.zeros((n_customers, n_total_vars))

    for i in range(n_customers):
        for j in range(n_facilities):
            var_index = i * n_facilities + j  # indice variabile x_ij
            A_assignment[i, var_index] = 1

    # 2. Vincoli di linking: x_ij <= y_j
    # Riscritti come x_ij - y_j <= 0
    A_linking = np.zeros((n_customers * n_facilities, n_total_vars))

    constraint_idx = 0
    for i in range(n_customers):
        for j in range(n_facilities):
            var_x_idx = i * n_facilities + j  # indice x_ij
            var_y_idx = n_assignment_vars + j  # indice y_j

            A_linking[constraint_idx, var_x_idx] = 1  # coefficiente x_ij
            A_linking[constraint_idx, var_y_idx] = -1  # coefficiente y_j
            constraint_idx += 1

    # Combina i vincoli
    A = np.vstack([A_assignment, A_linking])

    # === VETTORE b ===
    b_assignment = np.ones(n_customers)  # ogni cliente deve essere servito
    b_linking = np.zeros(n_customers * n_facilities)  # vincoli x_ij <= y_j
    b = np.concatenate([b_assignment, b_linking])

    # === VETTORE c ===
    # Appiattisce la matrice dei costi di assegnamento
    assignment_costs = assignment_costs.reshape(n_customers, n_facilities)
    c_assignment = assignment_costs.flatten()  # costi x_ij
    c_facility = fixed_costs  # costi y_j
    c = np.concatenate([c_assignment, c_facility])

    return A, b, c
