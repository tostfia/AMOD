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
            self.ampl.set_option('solver', 'gurobi')  # Imposta il solver CPLEX come predefinito
    def load_instance_from_model(self, model):
        current_path = Path(__file__).parent.parent.parent
        self.ampl.read(current_path / "models" / "UFL2.mod")
        p = model.get_num_facilities()
        r = model.get_num_customers()

        self.ampl.param['p'] = p
        self.ampl.param['r'] = r


        fixed_costs = model.get_fixed_costs()
        assignment_costs = model.get_assignment_costs()

        # Validazione automatica già fatta dal modello
        if not assignment_costs:
            raise ValueError("assignment_costs è vuoto")

        # Trasponi se necessario (come nel codice originale)
        assignment_costs = list(map(list, zip(*assignment_costs)))

        setup_dict = {i: c for i, c in enumerate(fixed_costs,start=1)}
        allocation_dict = {
            (i+1, j+1): assignment_costs[i][j]
            for i in range(p)
            for j in range(r)
        }

        self.ampl.param['setup'].setValues(setup_dict)
        self.ampl.param['allocation'].setValues(allocation_dict)




    def solve_instance(self,model):
        """Risolve il rilassamento lineare"""
        print("Risoluzione del rilassamento lineare...")
        self.ampl.solve()
        print("Soluzione trovata.")
        if self.ampl.getValue("TotalCost") is not None:
            total_cost= self.ampl.getObjective("TotalCost").value()
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
        Name=Path(filename).name
        with open(opt_file_path, 'r') as file:
            next(file)  # Salta l'intestazione

            for line in file:
                parts = line.strip().split()
                if len(parts) == 2 and parts[0] == Name.replace(".txt",""):
                    try:
                        return float(parts[1])
                    except ValueError:
                        raise ValueError(f"Valore non valido per {filename}: {parts[1]}")

        raise FileNotFoundError(f"Nessun valore ottimale trovato per {filename}")




    def compare_with_optimal(self,filename,model, z_lp=None, z_opt=None):
        """Risolvi rilassamento e confronta con valore ottimo noto"""
        if z_lp is None:
            z_lp = self.solve_instance(model)
        if z_opt is None:
            z_opt = self.load_optimal_solution(filename)
        print(f"Valore rilassato (LP): {z_lp:.3f}")
        print(f"Valore ottimo noto   : {z_opt:.3f}")
        print(f"Gap assoluto         : {abs(z_opt - z_lp):.3f}")
        print(f"Gap relativo (%)     : {100 * (z_opt - z_lp) / z_opt:.2f}%")



