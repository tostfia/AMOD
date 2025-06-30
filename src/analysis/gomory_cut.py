import numpy as np
from analysis.LP import *
from typing import Dict, List, Tuple, Optional
import logging
import math


class gomoryCut:
    """
    Implementazione corretta dell'algoritmo di Gomory Cut usando il tableau del simplesso.
    """

    def __init__(self, model):
        self.model = model

        # Verifica che il modello abbia i metodi necessari
        required_methods = ['get_num_facilities', 'get_num_customers', 'get_fixed_costs', 'get_assignment_costs']
        for method in required_methods:
            if not hasattr(model, method):
                raise AttributeError(f"Il modello deve avere il metodo {method}")

        try:
            self.n_facilities = model.get_num_facilities()
            self.n_customers = model.get_num_customers()
        except Exception as e:
            print(f"DEBUG: Errore ottenendo dimensioni modello: {e}")
            raise

        print(f"DEBUG: Inizializzazione - Facilities: {self.n_facilities}, Customers: {self.n_customers}")

        if self.n_facilities <= 0 or self.n_customers <= 0:
            raise ValueError(f"Dimensioni invalide - Facilities: {self.n_facilities}, Customers: {self.n_customers}")

        # Costruisci la matrice del problema lineare
        try:
            self.A, self.b, self.c = self._build_lp_matrices()
            print(f"DEBUG: Matrici costruite - A: {self.A.shape}, b: {self.b.shape}, c: {self.c.shape}")
        except Exception as e:
            print(f"DEBUG: Errore costruzione matrici: {e}")
            raise

        # Variabili per il tableau
        self.tableau = None
        self.basic_vars = None
        self.non_basic_vars = None
        self.current_basis = None

        self.logger = logging.getLogger(__name__)

    def _build_lp_matrices(self):
        """
        Costruisce le matrici A, b, c per il problema UFL in forma standard.
        """
        p, r = self.n_facilities, self.n_customers
        print(f"DEBUG: Building LP matrices - p={p}, r={r}")

        # Numero di variabili: p (y) + p*r (x)
        n_vars = p + p * r
        print(f"DEBUG: Numero variabili: {n_vars}")

        # Numero di vincoli: r (domanda) + p*r (linking)
        n_constraints = r + p * r
        print(f"DEBUG: Numero vincoli: {n_constraints}")

        # Matrice dei vincoli A
        A = np.zeros((n_constraints, n_vars))
        b = np.zeros(n_constraints)

        # Vincoli di domanda: Σ_i x_ij = 1
        for j in range(r):
            for i in range(p):
                x_idx = p + i * r + j  # Indice di x_ij
                if x_idx >= n_vars:
                    raise ValueError(f"Indice x_ij fuori bounds: {x_idx} >= {n_vars}")
                A[j, x_idx] = 1
            b[j] = 1

        # Vincoli di linking: x_ij - y_i <= 0
        constraint_idx = r
        for i in range(p):
            for j in range(r):
                x_idx = p + i * r + j  # Indice di x_ij
                y_idx = i  # Indice di y_i

                if x_idx >= n_vars or y_idx >= n_vars:
                    raise ValueError(f"Indici fuori bounds: x_idx={x_idx}, y_idx={y_idx}, n_vars={n_vars}")

                if constraint_idx >= n_constraints:
                    raise ValueError(f"Constraint index fuori bounds: {constraint_idx} >= {n_constraints}")

                A[constraint_idx, x_idx] = 1
                A[constraint_idx, y_idx] = -1
                b[constraint_idx] = 0

                constraint_idx += 1

        # Funzione obiettivo
        c = np.zeros(n_vars)

        # Coefficienti per y_i (costi fissi)
        try:
            fixed_costs = self.model.get_fixed_costs()
            print(f"DEBUG: Fixed costs length: {len(fixed_costs)}")
            for i in range(p):
                c[i] = fixed_costs[i]
        except Exception as e:
            print(f"DEBUG: Errore fixed costs: {e}")
            raise

        # Coefficienti per x_ij (costi di allocazione)
        try:
            assignment_costs = self.model.get_assignment_costs()
            print(
                f"DEBUG: Assignment costs shape: {len(assignment_costs)} x {len(assignment_costs[0]) if assignment_costs else 0}")

            # Verifica la strutura dei dati
            if len(assignment_costs) == r and len(assignment_costs[0]) == p:
                # I dati sono in formato [customer][facility], dobbiamo invertire
                print("DEBUG: Dati in formato [customer][facility], inversione necessaria")
                for i in range(p):
                    for j in range(r):
                        x_idx = p + i * r + j
                        if x_idx >= n_vars:
                            raise ValueError(f"Assignment cost index fuori bounds: {x_idx} >= {n_vars}")
                        c[x_idx] = assignment_costs[j][i]  # Inversione: [j][i] invece di [i][j]
            elif len(assignment_costs) == p and len(assignment_costs[0]) == r:
                # I dati sono già nel formato corretto [facility][customer]
                print("DEBUG: Dati in formato [facility][customer], nessuna inversione necessaria")
                for i in range(p):
                    for j in range(r):
                        x_idx = p + i * r + j
                        if x_idx >= n_vars:
                            raise ValueError(f"Assignment cost index fuori bounds: {x_idx} >= {n_vars}")
                        c[x_idx] = assignment_costs[i][j]
            else:
                raise ValueError(
                    f"Dimensioni assignment_costs non valide: {len(assignment_costs)} x {len(assignment_costs[0]) if assignment_costs else 0}, aspettate {p}x{r} o {r}x{p}")

        except Exception as e:
            print(f"DEBUG: Errore assignment costs: {e}")
            raise

        print(f"DEBUG: Matrici costruite con successo")
        return A, b, c

    def _solve_with_simplex(self):
        """
        Risolve il rilassamento lineare usando scipy.linprog.
        """
        try:

            solver = UFLSolver()
            solver.load_instance_from_model(self.model)
            result = solver.solve_instance()
            self._analyze_solution_integrality(result)

            return result

        except Exception as e:
            self.logger.error(f"Errore nella risoluzione del simplesso: {e}")
            raise

    def _analyze_solution_integrality(self, solution, tolerance=1e-6):
        """
        Analizza l'integralità della soluzione e stampa dettagli.
        """
        fractional_vars = []

        print(f"DEBUG: Analisi integralità soluzione:")

        # Controlla variabili y (facilities)
        for i in range(self.n_facilities):
            value = solution[i]
            fract_part = abs(value - round(value))
            if fract_part > tolerance:
                fractional_vars.append((f"y_{i}", value, fract_part))

        # Controlla variabili x (allocazioni) - solo alcune per non sovraccaricare
        sample_size = min(20, self.n_facilities * self.n_customers)
        for idx in range(sample_size):
            i = idx // self.n_customers
            j = idx % self.n_customers
            x_idx = self.n_facilities + i * self.n_customers + j
            if x_idx < len(solution):
                value = solution[x_idx]
                fract_part = abs(value - round(value))
                if fract_part > tolerance:
                    fractional_vars.append((f"x_{i}_{j}", value, fract_part))

        print(f"DEBUG: Trovate {len(fractional_vars)} variabili frazionarie (campione)")
        if fractional_vars:
            print("DEBUG: Prime 10 variabili frazionarie:")
            for i, (var_name, value, fract_part) in enumerate(fractional_vars[:10]):
                print(f"  {var_name}: {value:.6f} (frazione: {fract_part:.6f})")

        return len(fractional_vars) == 0

    def _is_integer_solution(self, solution, tolerance=1e-6):
        """
        Verifica se la soluzione è intera con tolleranza corretta.
        """
        try:
            fractional_count = 0
            for i, value in enumerate(solution):
                fract_part = abs(value - round(value))
                if fract_part > tolerance:
                    fractional_count += 1
                    # Stampa solo le prime variabili frazionarie per debug
                    if fractional_count <= 5:
                        var_type = "y" if i < self.n_facilities else "x"
                        print(f"DEBUG: Variabile frazionaria {var_type}_{i}: {value:.6f}")

            is_integer = fractional_count == 0
            print(f"DEBUG: Soluzione intera: {is_integer} (variabili frazionarie: {fractional_count})")
            return is_integer

        except Exception as e:
            self.logger.error(f"Errore verifica soluzione intera: {e}")
            return False

    def _find_most_fractional_variable(self, solution, tolerance=1e-6):
        """
        Trova la variabile con la parte frazionaria più grande.
        Restituisce (indice_variabile, valore, parte_frazionaria).
        """
        max_fract = 0
        best_var_idx = None
        best_value = None

        for i, value in enumerate(solution):
            fract_part = abs(value - round(value))
            # Considera solo variabili con frazione significativa e non troppo vicine a 0 o 1
            if fract_part > tolerance and fract_part > max_fract:
                max_fract = fract_part
                best_var_idx = i
                best_value = value

        if best_var_idx is not None:
            print(
                f"DEBUG: Variabile più frazionaria: indice {best_var_idx}, valore {best_value:.6f}, frazione {max_fract:.6f}")
            return best_var_idx, best_value, max_fract
        else:
            print("DEBUG: Nessuna variabile frazionaria significativa trovata")
            return None

    def _generate_simple_gomory_cut(self, var_idx, value):
        """
        Genera un semplice taglio di Gomory: x_i <= floor(value) oppure x_i >= ceil(value).
        Scegliamo x_i <= floor(value) per tagliare la soluzione corrente.
        """
        try:
            floor_value = math.floor(value)

            # Crea il vettore dei coefficienti del taglio
            cut_coeffs = np.zeros(len(self.c))
            cut_coeffs[var_idx] = 1

            # Il taglio è: x_var_idx <= floor_value
            print(f"DEBUG: Generato taglio semplice: x_{var_idx} <= {floor_value}")

            return cut_coeffs, floor_value

        except Exception as e:
            self.logger.error(f"Errore generazione taglio semplice: {e}")
            return None

    def _add_cut_to_problem(self, cut_coeffs, cut_rhs):
        """
        Aggiunge un taglio al problema lineare (aggiorna matrici A, b).
        Il taglio è nella forma: cut_coeffs * x <= cut_rhs
        """
        try:
            # Aggiungi il taglio come vincolo di disuguaglianza
            self.A = np.vstack([self.A, cut_coeffs.reshape(1, -1)])
            self.b = np.append(self.b, cut_rhs)

            print(f"DEBUG: Taglio aggiunto - Nuove dimensioni A: {self.A.shape}, b: {self.b.shape}")

        except Exception as e:
            self.logger.error(f"Errore aggiunta taglio: {e}")
            raise

    def solve_with_gomory_cuts(self, max_iterations):
        """
        Risolve il problema UFL con tagli di Gomory.
        """
        print(f"DEBUG: Iniziando Gomory cuts con max_iterations={max_iterations}")
        iteration = 0
        cuts_added = 0
        best_obj_value = float('inf')
        best_solution = None

        try:
            while iteration < max_iterations:
                iteration += 1
                print(f"\nDEBUG: ===== Iterazione {iteration} =====")

                # Risolvi il rilassamento lineare corrente
                try:
                    obj_value, solution = self._solve_with_simplex()
                    print(f"DEBUG: Soluzione trovata - obj_value={obj_value:.6f}")

                    # Tieni traccia della migliore soluzione
                    if obj_value < best_obj_value:
                        best_obj_value = obj_value
                        best_solution = solution.copy()

                except Exception as e:
                    print(f"DEBUG: Errore nel simplesso: {e}")
                    raise

                self.logger.info(f"Iterazione {iteration}: Obiettivo = {obj_value:.6f}")

                # Verifica se la soluzione è intera
                if self._is_integer_solution(solution):
                    self.logger.info(f"Soluzione intera trovata dopo {iteration} iterazioni!")
                    return self._format_solution(solution, obj_value, iteration, cuts_added, success=True)

                # Trova la variabile più frazionaria
                print(f"DEBUG: Cercando variabile più frazionaria...")
                fract_result = self._find_most_fractional_variable(solution)
                if fract_result is None:
                    print(f"DEBUG: Nessuna variabile frazionaria trovata - terminazione")
                    self.logger.warning("Nessuna variabile frazionaria significativa trovata")
                    break

                var_idx, var_value, fract_part = fract_result

                # Genera taglio semplice
                cut_result = self._generate_simple_gomory_cut(var_idx, var_value)
                if cut_result is None:
                    print(f"DEBUG: Impossibile generare taglio")
                    self.logger.warning("Impossibile generare taglio di Gomory")
                    break

                cut_coeffs, cut_rhs = cut_result
                print(f"DEBUG: Taglio generato - rhs={cut_rhs}")

                # Aggiungi il taglio al problema
                self._add_cut_to_problem(cut_coeffs, cut_rhs)
                cuts_added += 1

                self.logger.info(f"Aggiunto taglio #{cuts_added}: x_{var_idx} <= {cut_rhs}")

        except Exception as e:
            print(f"DEBUG: Errore durante Gomory cuts: {e}")
            import traceback
            traceback.print_exc()
            self.logger.error(f"Errore durante l'esecuzione Gomory cuts: {e}")

            # Usa la migliore soluzione trovata finora
            if best_solution is not None:
                return self._format_solution(best_solution, best_obj_value, iteration, cuts_added, success=False)
            else:
                return self._format_solution(np.array([]), float('inf'), iteration, cuts_added, success=False)

        # Limite di iterazioni raggiunto o nessuna variabile frazionaria
        final_solution = best_solution if best_solution is not None else solution
        final_obj = best_obj_value if best_solution is not None else obj_value

        print(f"DEBUG: Terminazione - iterazioni: {iteration}, tagli: {cuts_added}")
        return self._format_solution(final_solution, final_obj, iteration, cuts_added, success=False)

    def _format_solution(self, solution, obj_value, iterations, cuts, success=True):
        """Formatta la soluzione per l'output"""
        try:
            p, r = self.n_facilities, self.n_customers
            print(f"DEBUG: Formattando soluzione - p={p}, r={r}, solution_length={len(solution)}")

            # Estrai facility aperte
            open_facilities = []
            if len(solution) >= p:
                for i in range(p):
                    if solution[i] > 0.5:
                        open_facilities.append(i)

            print(f"DEBUG: Facilities aperte: {open_facilities}")

            # Estrai allocazioni
            allocations = {}
            if len(solution) >= p + p * r:
                for j in range(r):
                    for i in range(p):
                        x_idx = p + i * r + j
                        if x_idx < len(solution) and solution[x_idx] > 0.5:
                            allocations[j] = i
                            break

            print(f"DEBUG: Allocazioni: {len(allocations)} clienti allocati")

            # Verifica se la soluzione è intera
            is_integer = self._is_integer_solution(solution) if len(solution) > 0 else False
            print(f"DEBUG: Soluzione intera: {is_integer}")

            result = {
                'success': success,
                'optimal_value': obj_value,
                'open_facilities': open_facilities,
                'allocations': allocations,
                'iterations': iterations,
                'cuts_added': cuts,
                'solution_vector': solution,
                'filename': "",
                'filepath': "",
                'is_integer_solution': is_integer,
                'n_facilities': p,
                'n_customers': r,
                'execution_time': 0.0,
                'method': 'Gomory Cuts'
            }

            print(f"DEBUG: Risultato formattato con successo")
            return result

        except Exception as e:
            print(f"DEBUG: Errore formattazione soluzione: {e}")
            import traceback
            traceback.print_exc()
            self.logger.error(f"Errore formattazione soluzione: {e}")
            return {
                'success': False,
                'optimal_value': float('inf'),
                'open_facilities': [],
                'allocations': {},
                'iterations': iterations if 'iterations' in locals() else 0,
                'cuts_added': cuts if 'cuts' in locals() else 0,
                'solution_vector': np.array([]),
                'filename': "",
                'filepath': "",
                'is_integer_solution': False,
                'n_facilities': self.n_facilities if hasattr(self, 'n_facilities') else 0,
                'n_customers': self.n_customers if hasattr(self, 'n_customers') else 0,
                'execution_time': 0.0,
                'method': 'Gomory Cuts'
            }
