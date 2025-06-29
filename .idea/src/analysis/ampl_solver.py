from amplpy import AMPL
from pathlib import Path
import pandas as pd
from facilityLocation import FacilityLocationModel
class UFLSolver:
    def __init__(self,ampl=None):
        if ampl:
            from amplpy import Environment
            ampl_env = Environment(ampl)
            self.ampl = AMPL(ampl_env)
        else:
            self.ampl = AMPL()
            self.ampl.set_option('solver', 'gurobi')  # Imposta il solver GUROBI come predefinito
    def load_instance_from_model(self, model):
        current_path = Path(__file__).parent.parent.parent
        self.ampl.read(current_path / "models" / "UFL.mod")
        I = model.get_num_facilities()
        C = model.get_num_customers()

        self.ampl.param['I'] = I
        self.ampl.param['C'] = C


        fixed_costs = model.get_fixed_costs()
        assignment_costs = model.get_assignment_costs()

        # Validazione corretta per liste/array
        if len(assignment_costs) == 0:
            raise ValueError("assignment_costs è vuoto")

        # Trasponi se necessario (come nel codice originale)
        assignment_costs = list(map(list, zip(*assignment_costs)))

        setup_dict = {i: c for i, c in enumerate(fixed_costs,start=1)}
        allocation_dict = {
            (i+1, j+1): assignment_costs[i][j]
            for i in range(I)
            for j in range(C)
        }

        self.ampl.param['setup_cost'].setValues(setup_dict)
        self.ampl.param['allocation_cost'].setValues(allocation_dict)




    def solve_instance(self):
        """Risolve il rilassamento lineare"""
        print("Risoluzione del rilassamento lineare...")
        self.ampl.solve()
        print("Soluzione trovata.")
        if self.ampl.getValue("costi_totali") is not None:
            total_cost= self.ampl.getObjective("costi_totali").value()
            x_values = self.ampl.getVariable("x").getValues()
            actived_facilities=[int(row[0]) for row in x_values if row[1] > 0.5]
            print(f"Valore obiettivo: {total_cost:.3f}")
            print(f"Impianti attivi: {actived_facilities}")

            return total_cost
        else:
            raise ValueError("Nessun valore obiettivo trovato. Verifica l'istanza e i dati caricati.")





    def load_optimal_solution(self, filename):
        """Carica la soluzione ottimale da un file"""
        current_path = Path(__file__).parent.parent.parent
        opt_file_path = current_path / "data" / "opt_values" / "uncapopt.txt"
        name=Path(filename).name
        with open(opt_file_path, 'r') as file:
            next(file)  # Salta l'intestazione

            for line in file:
                parts = line.strip().split()
                if len(parts) == 2 and parts[0] == name.replace(".txt",""):
                    try:
                        return parts[1]
                    except ValueError:
                        raise ValueError(f"Valore non valido per {filename}: {parts[1]}")

        raise FileNotFoundError(f"Nessun valore ottimale trovato per {filename}")






