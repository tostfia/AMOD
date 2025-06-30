from datetime import datetime
import random
from pathlib import Path
from utility.facilityLocation import FacilityLocationModel
from config import *
import numpy as np
from typing import Tuple

"""Metodi per generare randomicamente istanze di UFL"""


def getSeed():
    return int(datetime.now().timestamp()) % 1_000_000


def generateInstance(instance_num: int, num_facilities: int, num_customers: int):
    random.seed(getSeed())

    base_path = DATA_DIR / "instances" / "random"
    base_path.mkdir(parents=True, exist_ok=True)

    filename = base_path / f"{instance_num}.txt"
    with open(filename, "w") as f:
        f.write(f"{num_facilities} {num_customers}\n")
        fixed_costs = [random.randint(1, 100) for _ in range(num_facilities)]
        for cost in fixed_costs:
            f.write(f"{cost}\n")

        assignment_costs_matrix = []
        for _ in range(num_customers):
            costs = [random.randint(1, 100) for _ in range(num_facilities)]
            assignment_costs_matrix.append(costs)
            f.write(" ".join(map(str, costs)) + "\n")

    model = FacilityLocationModel(num_facilities, num_customers, fixed_costs, assignment_costs_matrix)
    return model


