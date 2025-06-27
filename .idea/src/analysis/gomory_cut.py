from typing import Dict, List, Tuple, Optional
import numpy as np
from dataclasses import dataclass
import logging

@dataclass
class CutInfo:
    """Informazioni su un taglio di Gomory"""
    coefficients: Dict[int, float]
    rhs: float
    iteration: int
    fractional_value: float

class GomoryCut:
    """Implementazione migliorata dei tagli di Gomory per problemi UFL"""

    def __init__(self, ampl_solver: 'UFLSolver' = None, max_iterations: int = 50, tolerance: float = 1e-6):
        self.ampl_solver = ampl_solver
        self.ampl = ampl_solver.ampl if ampl_solver else None
        self.cuts_added = []
        self.iteration_history = []
        self.max_iterations = max_iterations
        self.tolerance = tolerance
        self.logger = logging.getLogger(__name__)

    def solve_with_gomory_cuts(self, model: 'FacilityLocationModel', solver: 'UFLSolver'):
        """Risolve il problema utilizzando i tagli di Gomory"""
        print("=== RISOLUZIONE CON TAGLI DI GOMORY ===")
        print(f"Facilities: {model.get_num_facilities()}, Customers: {model.get_num_customers()}")
        print(f"Costi fissi: {model.get_fixed_costs()}")
        print()

        # Assegna il solver se non già fatto
        if self.ampl_solver is None:
            self.ampl_solver = solver
            self.ampl = solver.ampl

        current_solution = None
        best_objective = float('inf')
        for iteration in range(self.max_iterations):
            print(f"---- Iterazione {iteration + 1} ----")

            # Risolvi il problema corrente
            try:
                self.ampl.solve()
                if self.ampl.getValue("TotalCost") is None:
                    print("Errore: nessuna soluzione trovata")
                    break

                objective_value = self.ampl.getObjective("TotalCost").value()
                print(f"Valore funzione obiettivo: {objective_value:.6f}")

                # Estrai le variabili di decisione
                current_solution = self._extract_solution(model)

            except Exception as e:
                print(f"Errore nella risoluzione: {e}")
                break

            # Controlla se la soluzione è intera
            if self.is_integer_solution(current_solution):
                print("✓ Soluzione intera trovata!")
                self._print_solution(current_solution, model, objective_value)
                return current_solution, objective_value

            # Trova la variabile più frazionaria
            frac_var_info= self.find_most_fractional_variable(current_solution,model)

            if frac_var_idx is None:
                print("Nessuna variabile frazionaria trovata, terminazione.")
                break

            var_name, var_value, var_type= frac_var_info
            print(f"Variabile più frazionaria: {var_name} = {var_value:.6f}")

            # Genera e aggiungi il taglio di Gomory
            success = self._add_gomory_cut(var_name, model, iteration)

            if not success:
                print("Errore nell'aggiunta del taglio, terminazione.")
                break

            # Memorizza l'iterazione
            self.iteration_history.append({
                'iteration': iteration + 1,
                'objective': objective_value,
                'solution': current_solution.copy(),
                'fractional_var': frac_var_idx,
                'fractional_value': var_value
            })

            print()

        print("Numero massimo di iterazioni raggiunto senza trovare soluzione intera")
        if current_solution is not None:
            self._print_solution(current_solution, model, objective_value)
        return current_solution, objective_value if current_solution is not None else None

    def _extract_solution(self, model):
        """Estrae la soluzione corrente dalle variabili AMPL"""
        solution = []

        # Estrai variabili y (facilities)
        try:
            x_values = self.ampl.getVariable("x").getValues()
            y_values = self.ampl.getVariable("y").getValues()

            # Crea dizionari per accesso rapido
            x_dict = {}  # x[u] - facility u è aperta
            y_dict = {}  # y[u,v] - cliente v servito da facility u

            # Processa variabili x (facilities)
            for row in x_values.toPandas().itertuples():
                facility_idx = int(row.index0)  # Indice facility (base 1 in AMPL)
                value = float(row.x)
                x_dict[facility_idx] = value

            # Processa variabili y (assegnazioni)
            for row in y_values.toPandas().itertuples():
                facility_idx = int(row.index0)  # Facility index
                customer_idx = int(row.index1)  # Customer index
                value = float(row.y)
                y_dict[(facility_idx, customer_idx)] = value

            return x_dict, y_dict

        except Exception as e:
            print(f"Errore nell'estrazione della soluzione: {e}")
            return {}, {}

    def is_integer_solution(self, solution):
        """Verifica se la soluzione è intera"""
        if isinstance(solution, tuple):
            x_dict, y_dict = solution

            # Controlla variabili x
            for value in x_dict.values():
                if abs(value - round(value)) > self.tolerance:
                    return False

            # Controlla variabili y
            for value in y_dict.values():
                if abs(value - round(value)) > self.tolerance:
                    return False

            return True
        return False
    def find_most_fractional_variable(self, solution,model):
        """Trova la variabile con maggiore distanza da 0 o 1 - versione dettagliata"""
        if not isinstance(solution, tuple):
            return None

        x_dict, y_dict = solution
        max_fractional = 0
        best_var = None

        # Controlla variabili x (facilities)
        for facility_idx, value in x_dict.items():
            fractional_part = min(value - np.floor(value), np.ceil(value) - value)
            if fractional_part > max_fractional and fractional_part > self.tolerance:
                max_fractional = fractional_part
                best_var = (f"x[{facility_idx}]", value, "facility")

        # Controlla variabili y (assegnazioni)
        for (facility_idx, customer_idx), value in y_dict.items():
            fractional_part = min(value - np.floor(value), np.ceil(value) - value)
            if fractional_part > max_fractional and fractional_part > self.tolerance:
                max_fractional = fractional_part
                best_var = (f"y[{facility_idx},{customer_idx}]", value, "assignment")

        return best_var

    def _add_gomory_cut(self,var_name, var_value, model, iteration):
        """Aggiunge un taglio di Gomory direttamente al modello AMPL"""
        try:
            cut_name = f"gomory_cut_{iteration+1}"
            # Calcola la parte frazionaria
            fractional_part = var_value - np.floor(var_value)

            # Taglio di Gomory classico per variabili binarie/intere
            # Se x è frazionaria con valore f, aggiungi: x <= floor(f) oppure x >= ceil(f)

            if fractional_part < 0.5:
                # Forza verso il basso
                rhs = np.floor(var_value)
                constraint = f"subject to {cut_name}: {var_name} <= {rhs};"
                print(f"Taglio aggiunto: {var_name} <= {rhs}")
            else:
                # Forza verso l'alto
                rhs = np.ceil(var_value)
                constraint = f"subject to {cut_name}: {var_name} >= {rhs};"
                print(f"Taglio aggiunto: {var_name} >= {rhs}")

            # Aggiungi il vincolo al modello AMPL
            self.ampl.eval(constraint)

            # Memorizza il taglio
            self.cuts_added.append({
                'name': cut_name,
                'constraint': constraint,
                'variable': var_name,
                'value': var_value,
                'fractional_part': fractional_part,
                'iteration': iteration + 1
            })

            return True

        except Exception as e:
            print(f"Errore nell'aggiunta del taglio: {e}")
            import traceback
            traceback.print_exc()
            return False


    def _print_solution(self, solution, model, objective_value):
        """Stampa la soluzione in formato leggibile"""
        if not isinstance(solution, tuple):
            print("Errore: formato soluzione non valido")
            return

        x_dict, y_dict = solution

        print("\n=== SOLUZIONE FINALE ===")
        print(f"Valore obiettivo: {objective_value:.6f}")

        # Facilities aperte
        print("\nFacilities aperte:")
        total_fixed_cost = 0
        for facility_idx, value in x_dict.items():
            if value > 0.5:
                # Nota: gli indici in AMPL partono da 1, ma i costi potrebbero partire da 0
                cost_idx = facility_idx - 1 if facility_idx > 0 else 0
                if cost_idx < len(model.get_fixed_costs()):
                    cost = model.get_fixed_costs()[cost_idx]
                    total_fixed_cost += cost
                    print(f"  Facility {facility_idx}: x[{facility_idx}] = {value:.0f} (costo fisso: {cost})")

        # Assegnazioni clienti
        print("\nAssegnazioni clienti:")
        total_assignment_cost = 0
        for (facility_idx, customer_idx), value in y_dict.items():
            if value > 0.5:
                try:
                    # Converti indici AMPL (base 1) a indici Python (base 0)
                    cost = model.get_assignment_cost(customer_idx - 1, facility_idx - 1)
                    total_assignment_cost += cost
                    print(f"  Cliente {customer_idx} → Facility {facility_idx}: y[{facility_idx},{customer_idx}] = {value:.0f} (costo: {cost})")
                except:
                    print(f"  Cliente {customer_idx} → Facility {facility_idx}: y[{facility_idx},{customer_idx}] = {value:.0f}")

        print(f"\nCosto fisso totale: {total_fixed_cost}")
        print(f"Costo assegnazione totale: {total_assignment_cost}")
        print(f"Costo totale: {total_fixed_cost + total_assignment_cost}")
    def get_statistics(self):
        """Restituisce statistiche sui tagli aggiunti"""
        return {
            'total_cuts': len(self.cuts_added),
            'total_iterations': len(self.iteration_history),
            'cuts_info': self.cuts_added,
            'iteration_history': self.iteration_history
        }
    def reset(self):
        """Reset dello stato per una nuova esecuzione"""
        # IMPORTANTE: Rimuovi i tagli precedenti dal modello AMPL
        for cut in self.cuts_added:
            try:
                self.ampl.eval(f"drop {cut['name']};")
            except:
                pass  # Il vincolo potrebbe non esistere

        self.cuts_added.clear()
        self.iteration_history.clear()
        print("Stato Gomory reset - tagli precedenti rimossi")
