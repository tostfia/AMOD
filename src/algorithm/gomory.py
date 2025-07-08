import datetime
import cplex
import numpy as np
from algorithm.solver import Solver, print_solution
from config import *
from utility.facilityLocation import FacilityLocationModel
from utility.utils import get_statistics, modulus


def _print_analysis_results(instance_name: str, results: dict):
    """Metodo helper privato per stampare la tabella dei risultati."""
    print("\n" + "="*95)
    print(f"RISULTATI COMPARATIVI PER: {instance_name}")
    print("="*95)
    header = (f"{'Modalità':<20} | {'Stato':<22} | {'Obiettivo':>15} | "
              f"{'Gap (%)':>10} | {'Nodi':>8} | {'Tagli Gomory':>12} | {'Tempo (s)':>10}")
    print(header)
    print("-"*95)

    for mode_name, res in sorted(results.items()):
        obj_str = f"{res['objective']:.2f}" if isinstance(res['objective'], float) else res['objective']
        gap_str = f"{res['gap']:.4f}" if isinstance(res['gap'], float) else res['gap']

        row = (f"{mode_name:<20} | {res['status']:<22} | {obj_str:>15} | "
               f"{gap_str:>10} | {res['nodes']:>8} | {res['gomory_cuts']:>12} | {res['time_sec']:>10.2f}")
        print(row)
    print("="*95)




class Gomory:
    """
    Classe che incapsula l'intero algoritmo dei piani di taglio di Gomory.
    Contiene la logica per il ciclo iterativo e per la generazione
    di diverse famiglie di tagli.
    """
    def __init__(self, model: FacilityLocationModel):
        self.model = model
        self.solver = Solver(self.model)
        # Questo attributo è importante per distinguere le variabili originali
        # dalle variabili di slack/ausiliarie.
        self.n_cols_original = 0

    #metodi privati per la scelta della modalità di taglio

    def _generate_gomory_fractional_cuts(self, prob: cplex.Cplex):
        """Genera Tagli Frazionari di Gomory (GFC)."""
        generated_cuts = []
        try:
            basis_col_status, _ = prob.solution.basis.get_basis()
            values = prob.solution.get_values()

            basic_var_indices = [i for i, s in enumerate(basis_col_status) if s == prob.solution.basis.status.basic]
            non_basic_var_indices = [i for i, s in enumerate(basis_col_status) if not (s == prob.solution.basis.status.basic)]

            for var_idx in basic_var_indices:
                basic_var_value = values[var_idx]
                fractional_part = basic_var_value - np.floor(basic_var_value)

                if fractional_part > NUMERICAL_TOLERANCE and (1 - fractional_part) > NUMERICAL_TOLERANCE:
                    try:
                        # Ottiene la riga del tableau per la variabile di base corrente
                        tableau_row_coeffs = np.array(prob.solution.advanced.binvarow(var_idx))
                    except cplex.CplexError:
                        continue # Salta se non riesce a ottenere la riga

                    cut_indices, cut_coeffs = [], []
                    for j, non_basic_idx in enumerate(non_basic_var_indices):
                        f_j = tableau_row_coeffs[j] - np.floor(tableau_row_coeffs[j])
                        if f_j > NUMERICAL_TOLERANCE:
                            cut_indices.append(non_basic_idx)
                            cut_coeffs.append(f_j)

                    if cut_indices:
                        violation=fractional_part
                        generated_cuts.append({
                            'indices': cut_indices, 'coeffs': cut_coeffs,
                            'rhs':fractional_part, 'sense': 'G', 'violation': violation
                        })
        except cplex.CplexError as e:
            print(f"ERRORE CPLEX durante la generazione dei tagli GFC: {e}")

        return generated_cuts

    def _generate_gomory_mixed_integer_cuts(self, prob: cplex.Cplex):
        """Genera Tagli Misti Interi di Gomory (GMI)."""
        generated_cuts = []

        try:
            basis_col_status, _ = prob.solution.basis.get_basis()
            values = prob.solution.get_values()

            basic_var_indices = [i for i, s in enumerate(basis_col_status)
                                 if s == prob.solution.basis.status.basic] #cerco qualsiasi var di base come GFC
            non_basic_var_indices = [i for i, s in enumerate(basis_col_status)
                                     if not (s == prob.solution.basis.status.basic)]

            for var_idx in basic_var_indices:
                basic_var_value = values[var_idx]
                f_i = basic_var_value - np.floor(basic_var_value)

                if f_i > NUMERICAL_TOLERANCE and (1 - f_i) > NUMERICAL_TOLERANCE:
                    try:
                        tableau_row_coeffs = np.array(prob.solution.advanced.binvarow(var_idx))
                    except cplex.CplexError:
                        continue

                    cut_indices, cut_coeffs = [], []
                    for j, non_basic_idx in enumerate(non_basic_var_indices):
                        a_ij = tableau_row_coeffs[j]
                        f_j = a_ij - np.floor(a_ij)

                        # Formula del coefficiente GMI
                        if f_j <= f_i + NUMERICAL_TOLERANCE:
                            coeff = f_j
                        else:
                            if (1 - f_i) > NUMERICAL_TOLERANCE:
                                coeff = (f_i / (1 - f_i)) * (1 - f_j)
                            else:
                                continue # Coefficiente non calcolabile, salta

                        if abs(coeff) > NUMERICAL_TOLERANCE:
                            cut_indices.append(non_basic_idx)
                            cut_coeffs.append(coeff)

                    if cut_indices:

                        violation = f_i
                        generated_cuts.append({
                                'indices': cut_indices, 'coeffs': cut_coeffs,
                                'rhs':f_i, 'sense': 'G', 'violation': violation
                        })
        except cplex.CplexError as e:
            print(f"ERRORE CPLEX durante la generazione dei tagli GMI: {e}")

        return generated_cuts

    #metodo principlae di risoluzione

    def solve_problem(self, instance_path_str: str, cut_mode: str = 'GFC'):
        instance_path = Path(instance_path_str)
        name = instance_path.stem

        c, A, b = self.solver.get_problem_data(maximize=True)
        self.n_cols_original, n_rows = len(c), len(b)

        optimal_sol = self.solver.determine_optimal(instance_path, maximize=True)
        if optimal_sol is None: return []

        tot_stats = []
        try:
            with cplex.Cplex() as mkp:
                # 1. Setup del problema LP iniziale
                mkp.set_problem_type(mkp.problem_type.LP)
                mkp.set_problem_name(name + "_LP_Relaxation")
                mkp.objective.set_sense(mkp.objective.sense.maximize)
                mkp.parameters.preprocessing.presolve.set(0)
                mkp.parameters.lpmethod.set(mkp.parameters.lpmethod.values.primal)

                var_names = ["x" + str(i) for i in range(self.n_cols_original)]
                mkp.variables.add(obj=c, lb=[0.0] * self.n_cols_original, ub=[1.0] * self.n_cols_original, names=var_names)
                mkp.linear_constraints.add(
                    lin_expr=[cplex.SparsePair(ind=list(range(self.n_cols_original)), val=A[i]) for i in range(n_rows)],
                    rhs=b.tolist(), senses=['L'] * n_rows, names=[f"c{i}" for i in range(n_rows)]
                )

                # 2. Risoluzione del rilassamento LP iniziale
                start_time = datetime.datetime.now()
                mkp.solve()
                sol, sol_type, status = print_solution(mkp)
                elapsed_time = (datetime.datetime.now() - start_time).total_seconds() * 1000
                stats_iter_0 = get_statistics(name, self.n_cols_original, n_rows, optimal_sol, sol, sol_type, status, 0, elapsed_time, 0)
                tot_stats.append(stats_iter_0)

                if status != 'optimal':
                    print("ERRORE: Rilassamento iniziale non risolto ottimamente.")
                    return tot_stats

                # 3. Ciclo iterativo di aggiunta dei tagli
                iteration, total_time, num_total_cuts = 1, elapsed_time, 0
                MAX_TOTAL_CUTS = 500 # Limite di sicurezza sul numero totale di tagli

                while (total_time <= TIME_LIMIT and num_total_cuts <= MAX_TOTAL_CUTS and
                       modulus(sol, optimal_sol) / (abs(optimal_sol) + 1e-10) > THRESHOLD_GAP and
                       status == "optimal" and iteration <= MAX_ITERATIONS):

                    start_iteration_time = datetime.datetime.now()

                    # 3a. Genera i tagli usando i metodi della classe
                    cuts_to_process = []
                    if cut_mode == 'GFC':
                        cuts_to_process = self._generate_gomory_fractional_cuts(mkp)
                    elif cut_mode == 'GMI':
                        cuts_to_process = self._generate_gomory_mixed_integer_cuts(mkp)
                    elif cut_mode == 'BOTH':
                        cuts_to_process = self._generate_gomory_fractional_cuts(mkp) + self._generate_gomory_mixed_integer_cuts(mkp)
                    elif cut_mode == 'BEST':
                        cuts_to_process = self._generate_gomory_fractional_cuts(mkp) + self._generate_gomory_mixed_integer_cuts(mkp)

                    if not cuts_to_process:
                        print("STOP: Nessun nuovo taglio generato.")
                        break

                    # 3b. Seleziona i tagli migliori e aggiungili
                    cuts_to_process.sort(key=lambda x: x.get('violation', 0), reverse=True)
                    MAX_CUTS_PER_ITERATION = 10
                    cuts_to_add = cuts_to_process[:MAX_CUTS_PER_ITERATION]

                    print(f"Iterazione {iteration}: Aggiungendo {len(cuts_to_add)} nuovi tagli (tipo: {cut_mode}).")
                    num_total_cuts += len(cuts_to_add)
                    for i, cut_info in enumerate(cuts_to_add):
                        mkp.linear_constraints.add(
                            lin_expr=[cplex.SparsePair(ind=cut_info['indices'], val=cut_info['coeffs'])],
                            senses=[cut_info['sense']], rhs=[cut_info['rhs']],
                            names=[f"{cut_mode.lower()}_{iteration}_{i}"]
                        )

                    # 3c. Risolvi il modello aggiornato
                    mkp.solve()
                    sol, sol_type, status = print_solution(mkp)

                    # 3d. Raccogli statistiche
                    iteration_time = (datetime.datetime.now() - start_iteration_time).total_seconds() * 1000
                    total_time += iteration_time
                    current_stats = get_statistics(name, self.n_cols_original, n_rows + num_total_cuts, optimal_sol, sol, sol_type, status, num_total_cuts, total_time, iteration)
                    tot_stats.append(current_stats)

                    if status != 'optimal':
                        print(f"STOP: Il problema è diventato {status}.")
                        break
                    iteration += 1

                print(f"\n=== FINE RISOLUZIONE (MODALITÀ {cut_mode}) ===")
                return tot_stats

        except cplex.CplexError as e:
            print(f"ERRORE CPLEX in solve_problem: {e}")
            return tot_stats
        except Exception as e:
            print(f"ERRORE IMPREVISTO in solve_problem: {e}")
            raise