
from utility.facilityLocation import FacilityLocationModel
from config import *

from datetime import datetime
import random





def get_seed():
    return int(datetime.now().timestamp()) % 1_000_000


def generate_instance(instance_num: int, num_facilities: int, num_customers: int):
    random.seed(get_seed())

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


def get_statistics(nVar, nConstraints, optimal_sol, sol, sol_type, status, ncuts, elapsed_time, iterations):
    stats = []
    stats.append(nVar)
    stats.append(nConstraints)
    stats.append(optimal_sol)
    stats.append(sol)
    stats.append(sol_type)
    stats.append(status)
    stats.append(ncuts)
    stats.append(round(elapsed_time))
    stats.append(modulus(sol, optimal_sol))
    if optimal_sol == sol:
        stats.append(0)
    else:
        if optimal_sol == 0:
            stats.append(0)
        else:
            stats.append(modulus(sol, optimal_sol) / (optimal_sol + pow(10, -10)))
    stats.append(iterations)
    return stats


def modulus(x, y):
    return abs(x - y)


