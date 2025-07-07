
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path

# Imposta uno stile grafico consistente per tutto il modulo
plt.style.use('seaborn-v0_8-whitegrid')

def plot_single_instance_convergence(instance_stats: list[dict], output_file: Path):
    """
    Crea un grafico della convergenza del valore obiettivo per una SINGOLA istanza.
    """
    if not instance_stats or len(instance_stats) < 2:
        print(f"Dati insufficienti per il grafico di convergenza di {output_file.stem}.")
        return

    output_file.parent.mkdir(parents=True, exist_ok=True)

    # Estrazione sicura dei dati
    iterations = [s.get('iteration', i) for i, s in enumerate(instance_stats)]
    objective_values = [s.get('lp_solution') for s in instance_stats]
    optimal_value = instance_stats[0].get('optimal_ilp')
    initial_lp_value = instance_stats[0].get('lp_solution')

    # Filtra valori None che potrebbero causare errori nel plotting
    if any(v is None for v in objective_values):
        print(f"Dati di soluzione mancanti per {output_file.stem}, grafico non generato.")
        return

    plt.figure(figsize=(12, 7))

    plt.plot(iterations, objective_values, marker='o', linestyle='-', color='b', label='Valore LP con Tagli')

    if initial_lp_value is not None:
        plt.axhline(y=initial_lp_value, color='r', linestyle='--', label=f'LP Iniziale ({initial_lp_value:.2f})')
    if optimal_value is not None:
        plt.axhline(y=optimal_value, color='g', linestyle='--', label=f'Ottimo Intero ({optimal_value:.2f})')

    instance_name = instance_stats[0].get('instance_name', 'Sconosciuta')
    plt.title(f'Convergenza Tagli di Gomory - Istanza: {instance_name}')
    plt.xlabel('Numero di Iterazioni di Gomory')
    plt.ylabel('Valore Funzione Obiettivo (Massimizzazione)')
    plt.gca().xaxis.set_major_locator(plt.MaxNLocator(integer=True)) # Assicura tick interi
    plt.legend()
    plt.tight_layout()

    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"Grafico di convergenza per '{instance_name}' salvato in: {output_file}")


def save_summary_report(all_summaries: list[dict], output_dir: Path):
    """
    Funzione principale che prende i riassunti di tutte le istanze,
    salva un report CSV completo e genera i grafici comparativi.
    """
    if not all_summaries:
        print("Nessun riassunto da elaborare. Nessun report generato.")
        return

    # --- 1. Preparazione dei Dati e Salvataggio CSV ---

    # Crea un DataFrame pandas per una facile manipolazione
    df = pd.DataFrame(all_summaries).sort_values('instance_name').reset_index(drop=True)

    # Assicura che la directory di output esista
    output_dir.mkdir(parents=True, exist_ok=True)

    # Salva il report CSV
    csv_path = output_dir / "_summary_all_instances.csv"
    df.to_csv(csv_path, index=False, float_format='%.4f')
    print(f"\nReport CSV riassuntivo salvato in: {csv_path}")

    # --- 2. Grafico Comparativo: Chiusura del Gap (Linee) ---

    instance_names = df['instance_name']

    plt.figure(figsize=(16, 9))

    # Moltiplica per 100 per avere percentuali
    initial_gaps = df['initial_gap'] * 100
    final_gaps = df['final_gap'] * 100

    plt.plot(instance_names, initial_gaps, marker='o', linestyle='--', color='dodgerblue', label='Gap Iniziale (%)')
    plt.plot(instance_names, final_gaps, marker='s', linestyle='-', color='crimson', label='Gap Finale (%)')
    plt.fill_between(instance_names, initial_gaps, final_gaps, color='grey', alpha=0.2, label='Gap Chiuso')

    plt.title('Efficacia dei Tagli di Gomory: Riduzione del Gap Relativo', fontsize=16, fontweight='bold')
    plt.ylabel('Gap Relativo (%)', fontsize=12)
    plt.xlabel('Istanza del Problema', fontsize=12)
    plt.xticks(rotation=45, ha="right", fontsize=9)
    plt.yticks(fontsize=10)
    plt.legend(fontsize=11)
    plt.grid(True, which='both', linestyle='--', linewidth=0.5)
    plt.tight_layout()

    gap_plot_path = output_dir / "_comparative_gap_closure.png"
    plt.savefig(gap_plot_path, dpi=300)
    plt.close()
    print(f"Grafico comparativo sulla chiusura del gap salvato in: {gap_plot_path}")

    # --- 3. Grafico Comparativo: Costo Computazionale (Barre/Linee) ---

    fig, ax1 = plt.subplots(figsize=(16, 9))

    color = 'tab:blue'
    ax1.set_xlabel('Istanza del Problema', fontsize=12)
    ax1.set_ylabel('Numero di Iterazioni', color=color, fontsize=12)
    ax1.bar(instance_names, df['total_iterations'], color=color, alpha=0.6, label='Iterazioni')
    ax1.tick_params(axis='y', labelcolor=color)
    ax1.set_xticks(np.arange(len(df['instance_name']))) # Imposta le posizioni dei tick
    ax1.set_xticklabels(df['instance_name'], rotation=45, ha="right", fontsize=9)

    ax2 = ax1.twinx()
    color = 'tab:red'
    ax2.set_ylabel('Numero Totale di Tagli Aggiunti', color=color, fontsize=12)
    ax2.plot(instance_names, df['total_cuts'], color=color, marker='o', linestyle='--', label='Tagli Totali')
    ax2.tick_params(axis='y', labelcolor=color)

    plt.title('Costo Computazionale dei Tagli di Gomory', fontsize=16, fontweight='bold')
    fig.tight_layout()
    cost_plot_path = output_dir / "_comparative_computational_cost.png"
    plt.savefig(cost_plot_path, dpi=300)
    plt.close()
    print(f"Grafico comparativo sul costo computazionale salvato in: {cost_plot_path}")