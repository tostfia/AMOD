from amplpy import AMPL
from pathlib import Path
import pandas as pd
from utility.facilityLocation import *
from config import MODEL_DIR


class UFLSolver:
    def __init__(self):
        self.ampl = AMPL()
        self.ampl.set_option('solver', 'gurobi')  # Imposta il solver GUROBI come predefinito

    def load_instance_from_model(self, model):
        self.ampl.read(MODEL_DIR/ "rilassa_lineare.mod")
        p = model.get_num_facilities()
        r = model.get_num_customers()

        self.ampl.param['p'] = p
        self.ampl.param['r'] = r

        fixed_costs = model.get_fixed_costs()
        assignment_costs = model.get_assignment_costs()

        # Validazione corretta per liste/array
        if len(assignment_costs) == 0:
            raise ValueError("assignment_costs è vuoto")

        # Trasponi se necessario (come nel codice originale)
        assignment_costs = list(map(list, zip(*assignment_costs)))

        setup_dict = {i: c for i, c in enumerate(fixed_costs, start=1)}
        allocation_dict = {
            (i + 1, j + 1): assignment_costs[i][j]
            for i in range(p)
            for j in range(r)
        }

        self.ampl.param['setup'].setValues(setup_dict)
        self.ampl.param['allocation'].setValues(allocation_dict)

    def solve_instance(self):
        """Risolve il rilassamento lineare"""
        print("Risoluzione del rilassamento lineare...")
        self.ampl.solve()
        print("Soluzione trovata.")
        if self.ampl.getValue("TotalCost") is not None:
            total_cost = self.ampl.getObjective("TotalCost").value()
            x_values = self.ampl.getVariable("x").getValues()
            actived_facilities = [int(row[0]) for row in x_values if row[1] > 0.5]
            print(f"Soluzione rilassamento lineare: {total_cost:.3f}")
            print(f"Impianti attivi: {actived_facilities}")

            return total_cost
        else:
            raise ValueError("Nessun valore obiettivo trovato. Verifica l'istanza e i dati caricati.")
