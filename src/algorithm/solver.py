import numpy as np
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

        # --- VINCOLI ---
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
        Questa versione costruisce i vincoli direttamente per maggiore chiarezza ed efficienza.
        """
        p = self.model.get_num_facilities()
        r = self.model.get_num_customers()
        nCols = p + (r * p)
        name = instance_path.stem

        c, _, _ = self.get_problem_data(maximize=maximize)

        try:
            with cplex.Cplex() as mkp:
                mkp.set_problem_name(f"{name}_optimal_ILP")
                mkp.objective.set_sense(mkp.objective.sense.maximize if maximize else mkp.objective.sense.minimize)

                # Silenzia l'output di CPLEX
                mkp.set_log_stream(None)
                mkp.set_error_stream(None)
                mkp.set_warning_stream(None)
                mkp.set_results_stream(None)

                var_types = [mkp.variables.type.binary] * nCols
                var_names = ["x" + str(i) for i in range(nCols)]
                mkp.variables.add(obj=c.tolist(), names=var_names, types=var_types)



                constraints_to_add = []
                rhs_to_add = []
                senses_to_add = []

                # Vincoli di uguaglianza: sum_u y_uv = 1 per ogni cliente v
                for v in range(r):
                    row_indices = [p + u * r + v for u in range(p)]
                    row_values = [1.0] * p
                    constraints_to_add.append(cplex.SparsePair(ind=row_indices, val=row_values))
                    rhs_to_add.append(1.0)
                    senses_to_add.append('E') # 'E' per Equality

                # Vincoli di disuguaglianza: y_uv <= x_u  ->  y_uv - x_u <= 0
                for u in range(p):
                    for v in range(r):
                        row_indices = [p + u * r + v, u]
                        row_values = [1.0, -1.0]
                        constraints_to_add.append(cplex.SparsePair(ind=row_indices, val=row_values))
                        rhs_to_add.append(0.0)
                        senses_to_add.append('L') # 'L' per Less than or equal

                mkp.linear_constraints.add(
                    lin_expr=constraints_to_add,
                    rhs=rhs_to_add,
                    senses=senses_to_add
                )

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