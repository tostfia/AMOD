

import datetime
import cplex


from algorithm.solver import Solver, initialize_instance_variables, print_solution, generate_gomory_fractional_cuts
from config import *
from utility.facilityLocation import FacilityLocationModel
from utility.utils import get_statistics, modulus

def calculate_gap(current_sol, optimal_sol):
    """Calcola il gap relativo tra la soluzione corrente e quella ottima."""
    if optimal_sol is None or current_sol is None:
        return float('inf')
    # Per la massimizzazione, current_sol >= optimal_sol. Il gap è (current - optimal)
    # Per la minimizzazione, current_sol <= optimal_sol. Il gap è (optimal - current)
    # Usando abs() funziona in entrambi i casi.
    gap = abs(current_sol - optimal_sol)
    denominator = abs(optimal_sol) + 1e-10
    return gap / denominator

def setup_cplex_problem(mkp, name, c, A, b, lower_bounds, upper_bounds, constraint_senses, constraint_names):
    """Imposta il problema CPLEX per il rilassamento LP."""
    nCols = len(c)
    nRows = len(b)
    all_vars_names = ["x" + str(i) for i in range(nCols)] + ["s" + str(i) for i in range(nRows)]

    mkp.set_problem_name(name)
    mkp.objective.set_sense(mkp.objective.sense.maximize)

    params = mkp.parameters
    params.preprocessing.presolve.set(0)
    params.lpmethod.set(params.lpmethod.values.primal) # Usa Simplex Primale

    mkp.variables.add(names=all_vars_names, lb=lower_bounds, ub=upper_bounds + [cplex.infinity] * nRows)

    # Aggiungi i vincoli originali con le variabili di slack
    for i in range(nRows):
        row_indices = list(range(nCols)) + [nCols + i] # Aggiunge l'indice della slack var
        row_values = A[i].tolist() + [1.0] # Aggiunge il coefficiente della slack var
        mkp.linear_constraints.add(
            lin_expr=[cplex.SparsePair(ind=row_indices, val=row_values)],
            rhs=[b[i]],
            names=[constraint_names[i]],
            senses=['E'] # Ora i vincoli sono di uguaglianza grazie alle slack
        )

    mkp.objective.set_linear(list(enumerate(c)))

class Gomory:
    def __init__(self, model: FacilityLocationModel):
        self.model = model

    def solve_problem(self, instance_path_str: str):
        instance_path = Path(instance_path_str)
        print(f"\n=== INIZIO RISOLUZIONE (GOMORY SU MAXIMIZE): {instance_path.name} ===")
        solver = Solver(self.model)

        # 1. Ottieni i dati del problema come MASSIMIZZAZIONE
        c, A, b = solver.get_problem_data(maximize=True)
        nCols, nRows = len(c), len(b)

        name = instance_path.stem
        tot_stats = []

        # 2. Ottieni la soluzione ottima di riferimento (sempre in modalità massimizzazione)
        optimal_sol = solver.determine_optimal(instance_path, maximize=True)
        if optimal_sol is None:
            return []

        names, lower_bounds, upper_bounds, constraint_senses, constraint_names = initialize_instance_variables(nCols, nRows)

        try:
            with cplex.Cplex() as mkp:
                # 3. Setup del problema LP iniziale (massimizzazione)
                # Dobbiamo creare un modello con slack esplicite per accedere al tableau

                mkp.set_problem_type(mkp.problem_type.LP)
                mkp.set_problem_name(name)
                mkp.objective.set_sense(mkp.objective.sense.maximize)
                params = mkp.parameters
                params.preprocessing.presolve.set(0)
                params.lpmethod.set(params.lpmethod.values.primal)
                params.simplex.tolerance.feasibilty.set(1e-9)
                var_names = ["x" + str(i) for i in range(nCols)]

                # Definiamo i tipi di variabili. Per il rilassamento LP,
                # tutte le variabili devono essere CONTINUE.
                var_types = [mkp.variables.type.continuous] * (nCols + nRows)

                mkp.variables.add(
                    obj=c,
                    lb=[0.0] * (nCols),
                    ub=[1.0] * nCols, # Bound per le variabili binarie originali
                    names=var_names
                )
                mkp.linear_constraints.add(
                    lin_expr=[cplex.SparsePair(ind=list(range(nCols + nRows)), val=A[i]) for i in range(nRows)],
                    rhs=b.tolist(),
                    senses=['L'] * nRows,
                    names=["c"+str(i) for i in range(nRows)]# Vincoli di uguaglianza
                )

                # 4. Risolvi il rilassamento iniziale
                print("\n--- RISOLUZIONE RILASSAMENTO INIZIALE ---")
                start_time = datetime.datetime.now()
                mkp.solve()
                sol, sol_type, status = print_solution(mkp)
                elapsed_time = (datetime.datetime.now() - start_time).total_seconds() * 1000

                # Aggiungi statistiche iniziali
                stats_iter_0 = get_statistics(name, nCols, nRows, optimal_sol, sol, sol_type, status, 0, elapsed_time, 0)
                tot_stats.append(stats_iter_0)

                if status != 'optimal':
                    print("ERRORE: Rilassamento iniziale non risolto ottimamente.")
                    return tot_stats

                # 5. Ciclo di Gomory
                iteration = 1
                total_time = elapsed_time
                num_total_cuts = 0

                while (total_time <= TIME_LIMIT and
                       calculate_gap(sol, optimal_sol) > THRESHOLD_GAP and
                       status == "optimal" and iteration <= MAX_ITERATIONS):

                    print(f"\n### ITERAZIONE GOMORY {iteration} ###")
                    start_iteration_time = datetime.datetime.now()

                    # Genera nuovi tagli
                    new_cuts_data= generate_gomory_fractional_cuts(mkp, nCols)

                    if not new_cuts_data:
                        print("STOP: Nessun nuovo taglio frazionario generato. La soluzione potrebbe essere ottima intera.")
                        break

                    print(f"Generati {len(new_cuts_data)} nuovi tagli.")
                    num_total_cuts += len(new_cuts_data)
                    for i, cut_info in enumerate(new_cuts_data):
                        mkp.linear_constraints.add(
                            lin_expr=[cplex.SparsePair(ind=cut_info['indices'], val=cut_info['coeffs'])],
                            senses=[cut_info['sense']],
                            rhs=[cut_info['rhs']],
                            names=[f"gfc_{iteration}_{i}"]
                        )


                    # Risolvi il modello aggiornato
                    mkp.solve()
                    sol, sol_type, status = print_solution(mkp)

                    # Raccogli statistiche
                    iteration_time = (datetime.datetime.now() - start_iteration_time).total_seconds() * 1000
                    total_time += iteration_time
                    current_stats = get_statistics(name, nCols, nRows + num_total_cuts, optimal_sol, sol, sol_type, status, num_total_cuts, total_time, iteration)
                    tot_stats.append(current_stats)
                    print(f"Nuova soluzione: {sol:.4f}, status: {status}, gap: {current_stats.get('relative_gap', float('inf')):.4f}")

                    if status != 'optimal':
                        print(f"STOP: Il problema è diventato {status}.")
                        break

                    iteration += 1

                print(f"\n=== FINE RISOLUZIONE ===")
                print(f"Iterazioni totali: {iteration - 1}, Tagli totali: {num_total_cuts}")
                # Stampa il risultato finale riconvertito in MINIMIZZAZIONE
                if sol is not None:
                    print(f"Valore finale (MAX): {sol:.4f} -> Valore finale (MIN): {-sol:.4f}")

                return tot_stats

        except cplex.CplexError as e:
            print(f"ERRORE CPLEX in solve_problem: {e}")
            return tot_stats
        except Exception as e:
            print(f"ERRORE IMPREVISTO in solve_problem: {e}")
            raise # Rilancia l'eccezione per un debug più facile
            return tot_stats