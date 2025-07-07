
import os
import numpy as np
import logging
import cplex
from pathlib import Path
from utility.facilityLocation import FacilityLocationModel

def print_solution(prob: cplex.Cplex()):
    """Stampa la soluzione di un problema CPLEX in modo leggibile."""
    try:
        sol_status_str = prob.solution.get_status_string()
        obj_value = prob.solution.get_objective_value()

        print(f"Solution status = {sol_status_str}")
        print(f"Solution value  = {obj_value:.4f}")

        sol_type = abs(obj_value - round(obj_value)) < 1e-6
        return obj_value, sol_type, sol_status_str

    except cplex.CplexError:
        try:
            sol_status_str = prob.solution.get_status_string()
            print(f"Solution status = {sol_status_str}")
            return None, False, sol_status_str
        except cplex.CplexError as e:
            print(f"Errore critico durante il recupero della soluzione: {e}")
            return None, False, "error"

def initialize_instance_variables(nCols, nRows):
    """Inizializza i nomi e i bound per le variabili e i vincoli."""
    names = ["x" + str(i) for i in range(nCols)] + ["s" + str(i) for i in range(nRows)]
    lower_bounds = [0.0] * (nCols + nRows)
    upper_bounds = [1.0] * nCols # Upper bound solo per le variabili originali binarie

    constraint_names = ["c" + str(i) for i in range(nRows)]
    constraint_senses = ["L"] * nRows

    return names, lower_bounds, upper_bounds, constraint_senses, constraint_names




# In analysis/solver.py

def generate_gomory_fractional_cuts(prob: cplex.Cplex, num_original_vars: int):
    """
    Genera Tagli Frazionari di Gomory per un problema di MASSIMIZZAZIONE.
    Versione matematicamente corretta che costruisce i tagli solo
    sulle variabili non di base.
    """
    generated_cuts = []
    NUMERICAL_TOLERANCE = 1e-6

    try:
        # 1. Ottieni le informazioni di base
        basis_col_status, _ = prob.solution.basis.get_basis()
        values = prob.solution.get_values()

        # 2. Identifica gli indici delle variabili DI BASE e NON DI BASE
        basic_var_indices = [i for i, s in enumerate(basis_col_status) if s == prob.solution.basis.status.basic]
        non_basic_var_indices = [i for i, s in enumerate(basis_col_status) if s == prob.solution.basis.status.at_lower_bound or s == prob.solution.basis.status.at_upper_bound]

        # 3. Itera sulle variabili di base per trovare quelle frazionarie
        for var_idx in basic_var_indices:
            basic_var_value = values[var_idx]
            fractional_part = basic_var_value - np.floor(basic_var_value)

            if fractional_part > NUMERICAL_TOLERANCE and (1 - fractional_part) > NUMERICAL_TOLERANCE:
                # Trovata una riga candidata per il taglio

                # 4. Ottieni la riga del tableau corrispondente
                try:
                    row_idx = basic_var_indices.index(var_idx)
                    tableau_row_coeffs = np.array(prob.solution.advanced.binvarow(row_idx))
                except (ValueError, cplex.CplexError) as e:
                    print(f"Avviso: impossibile ottenere la riga del tableau per la variabile di base {var_idx}. Errore: {e}")
                    continue

                f_i = fractional_part

                # --- INIZIO CORREZIONE FONDAMENTALE ---

                # 5. Costruisci il taglio in termini di variabili NON DI BASE
                cut_indices = []
                cut_coeffs = []

                # tableau_row_coeffs ha tanti elementi quante sono le variabili non di base.
                # L'elemento j-esimo di tableau_row_coeffs è il coefficiente della j-esima variabile non di base.
                for j, non_basic_idx in enumerate(non_basic_var_indices):
                    # Consideriamo solo le variabili originali, non le slack non di base
                    if non_basic_idx < num_original_vars:
                        # Calcola la parte frazionaria del coefficiente
                        f_j = tableau_row_coeffs[j] - np.floor(tableau_row_coeffs[j])

                        # Aggiungiamo solo se il coefficiente non è trascurabile
                        if f_j > NUMERICAL_TOLERANCE:
                            cut_indices.append(non_basic_idx)
                            cut_coeffs.append(f_j)

                # 6. Se il taglio non è vuoto, salvalo
                # Il taglio è sum(f_j * x_j_non_base) >= f_i
                if cut_indices:
                    # In forma standard (<=): -sum(f_j * x_j_non_base) <= -f_i
                    lhs_coeffs = [-c for c in cut_coeffs]
                    rhs_val = -f_i

                    # Creiamo un dizionario completo per il taglio
                    cut_dict = {
                        'indices': cut_indices, # Indici delle variabili nel taglio
                        'coeffs': lhs_coeffs,   # Loro coefficienti
                        'rhs': rhs_val,
                        'sense': 'L',
                        'violation': f_i
                    }
                    generated_cuts.append(cut_dict)

                # --- FINE CORREZIONE FONDAMENTALE ---

    except cplex.CplexError as e:
        print(f"ERRORE CPLEX durante la generazione dei tagli: {e}")

    if not generated_cuts:
        return [], [], []

    # Ordina e seleziona i tagli migliori
    generated_cuts.sort(key=lambda x: x['violation'], reverse=True)
    MAX_CUTS_PER_ITERATION = 50
    num_to_add = min(len(generated_cuts), MAX_CUTS_PER_ITERATION)
    print(f"Generati {len(generated_cuts)} tagli validi, verranno aggiunti i {num_to_add} più violati.")

    return generated_cuts[:num_to_add]

class Solver:
    def __init__(self, model: FacilityLocationModel):
        self.model = model

    def get_problem_data(self, maximize=False):
        """
        Prepara i dati del problema UFL.
        Se maximize=True, inverte il segno del vettore dei costi `c`.
        """
        p = self.model.get_num_facilities()
        r = self.model.get_num_customers()
        fixed_costs = self.model.get_fixed_costs()
        assignment_costs = self.model.get_assignment_costs()
        n_vars = p + (r * p)

        c = np.zeros(n_vars, dtype=np.float64)
        c[:p] = [float(cost) for cost in fixed_costs]
        for u in range(p):
            for v in range(r):
                c[p + u * r + v] = float(assignment_costs[v][u])

        # --- TRASFORMAZIONE IN MASSIMIZZAZIONE ---
        if maximize:
            c = -c

        # --- VINCOLI (rimangono invariati) ---
        A_list = []
        b_list = []
        # Vincoli: sum_u y_uv = 1 per ogni cliente v
        for v in range(r):
            row = np.zeros(n_vars, dtype=np.float64)
            for u in range(p):
                row[p + u * r + v] = 1.0
            A_list.append(row.tolist())
            b_list.append(1.0)
            A_list.append((-row).tolist()) # Per forzare l'uguaglianza
            b_list.append(-1.0)

        # Vincoli: y_uv <= x_u  ->  y_uv - x_u <= 0
        for u in range(p):
            for v in range(r):
                row = np.zeros(n_vars, dtype=np.float64)
                row[p + u * r + v] = 1.0
                row[u] = -1.0
                A_list.append(row.tolist())
                b_list.append(0.0)

        A = np.array(A_list, dtype=np.float64)
        b = np.array(b_list, dtype=np.float64)
        return c, A, b

    def determine_optimal(self, instance_path: Path, maximize=False):
        """
        Risolve l'ILP per trovare la soluzione ottima di riferimento.
        """
        c, A, b = self.get_problem_data(maximize=maximize)
        nCols = len(c)
        name = instance_path.stem

        try:
            with cplex.Cplex() as mkp:
                mkp.set_problem_name(f"{name}_optimal_ILP")
                mkp.objective.set_sense(mkp.objective.sense.maximize if maximize else mkp.objective.sense.minimize)

                # Silenzia l'output di CPLEX
                mkp.set_log_stream(None)
                mkp.set_error_stream(None)
                mkp.set_warning_stream(None)
                mkp.set_results_stream(None)

                var_names = ["x" + str(i) for i in range(nCols)]
                mkp.variables.add(names=var_names, types=[mkp.variables.type.binary] * nCols)

                constraint_senses = ["L"] * len(b)
                mkp.linear_constraints.add(
                    lin_expr=[cplex.SparsePair(ind=list(range(nCols)), val=A[i]) for i in range(len(b))],
                    rhs=b.tolist(),
                    senses=constraint_senses
                )

                mkp.objective.set_linear(list(enumerate(c)))

                print(f"Risolvendo ILP per {name} per trovare l'ottimo di riferimento...")
                mkp.solve()

                if mkp.solution.get_status() in [101, 102]: # 101=optimal, 102=optimal integer
                    optimal_sol = mkp.solution.get_objective_value()
                    print(f"Soluzione ottima di riferimento trovata. Valore: {optimal_sol:.4f}")
                    return optimal_sol
                else:
                    print(f"ATTENZIONE: Soluzione ottima non trovata. Status: {mkp.solution.get_status_string()}")
                    return None
        except cplex.CplexError as e:
            print(f"Errore CPLEX in determine_optimal: {e}")
            return None