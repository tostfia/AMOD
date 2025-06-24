from amplpy import AMPL
from pathlib import Path
import pandas as pd
class UFLSolver:
    def __init__(self,ampl=None):
        if ampl:
            from amplpy import Environment
            ampl_env = Environment(ampl)
            self.ampl = AMPL(ampl_env)
        else:
            self.ampl = AMPL()
            self.ampl.set_option('solver', 'gurobi')  # Imposta il solver CPLEX come predefinito
    def load_instance(self, instance_data):
        current_path = Path(__file__).parent.parent.parent
        self.ampl.read(current_path / "models" / "UFL2.mod")

        p = instance_data['num_facilities']
        r = instance_data['num_customers']

        self.ampl.param['p'] = p
        self.ampl.param['r'] = r


        # Validazione preliminare
        if not instance_data['assignment_costs']:
            raise ValueError("assignment_costs è vuoto")
        # Trasponi la matrice se servono 16 righe e 50 colonne
        instance_data['assignment_costs'] = list(map(list, zip(*instance_data['assignment_costs'])))

        p = len(instance_data['fixed_costs'])
        r = len(instance_data['assignment_costs'][0])

        if len(instance_data['assignment_costs']) != p:
            raise ValueError(f"assignment_costs ha {len(instance_data['assignment_costs'])} righe, ma fixed_costs ha {p} elementi")

        for i, row in enumerate(instance_data['assignment_costs']):
            if len(row) != r:
                raise ValueError(f"Riga {i} di assignment_costs ha {len(row)} colonne, attese {r}")



        setup_dict = {i: c for i, c in enumerate(instance_data['fixed_costs'], start=1)}
        allocation_dict = {
            (i+1, j+1): instance_data['assignment_costs'][i][j]
            for i in range(p)
            for j in range(r)
        }

        self.ampl.param['setup'].setValues(setup_dict)
        self.ampl.param['allocation'].setValues(allocation_dict)



    def solve_instance(self,instance_data):
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




    def compare_with_optimal(self,filename,instance_data, z_lp=None, z_opt=None):
        """Risolvi rilassamento e confronta con valore ottimo noto"""
        if z_lp is None:
            z_lp = self.solve_instance(instance_data)
        if z_opt is None:
            z_opt = self.load_optimal_solution(filename)
        print(f"Valore rilassato (LP): {z_lp:.3f}")
        print(f"Valore ottimo noto   : {z_opt:.3f}")
        print(f"Gap assoluto         : {abs(z_opt - z_lp):.3f}")
        print(f"Gap relativo (%)     : {100 * (z_opt - z_lp) / z_opt:.2f}%")



""" def solve_with_gomory(self, max_iterations=100):
        Implementa i Gomory cuts
        iteration = 0

        while iteration < max_iterations:
            # Risolvi il problema corrente
            result = self.solve_linear_relaxation()

            # Controlla se la soluzione è intera
            if self.is_integer_solution(result):
                return result

            # Aggiungi Gomory cut
            self.add_gomory_cut(result)
            iteration += 1

        return result

    def is_integer_solution(self, solution, tolerance=1e-6):
        Verifica se la soluzione è intera
        for value in solution['x_values'].values():
            if abs(value - round(value)) > tolerance:
                return False
        return True

    def add_gomory_cut(self, solution):
        Aggiunge un taglio di Gomory
        # Trova la variabile più frazionaria
        max_frac = 0
        cut_var = None

        for var, value in solution['x_values'].items():
            frac = min(value - int(value), int(value) + 1 - value)
            if frac > max_frac:
                max_frac = frac
                cut_var = var

        if cut_var:
            # Aggiungi il taglio (implementazione semplificata)
            cut_name = f"gomory_cut_{len(self.ampl.getConstraints())}"
            # Qui dovresti implementare la logica completa del taglio di Gomory
            pass """