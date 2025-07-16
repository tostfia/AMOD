import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns
from pathlib import Path
plt.style.use('seaborn-v0_8-whitegrid')
sns.set_palette('muted')

def clean_instance_name(name: str) -> str:
    """Pulisce i nomi delle istanze per una migliore visualizzazione nei grafici."""
    name = name.replace("instance_", "")
    name = name.replace("UFL_", "")
    # Gestisce sia i nomi con UUID che quelli con contatore numerico
    parts = name.split('_')
    if len(parts) > 1 and len(parts[-1]) > 6: # Probabilmente un UUID o hash lungo
        return f"{parts[0]}_{parts[-1][:4]}" # Abbrevia l'identificatore univoco
    return name




def plot_single_instance_convergence(instance_stats: list[dict], output_file: Path):
    """
    Crea un grafico della convergenza del valore obiettivo per una SINGOLA istanza.
    """
    if not instance_stats:
        print(f"Dati insufficienti per il grafico di convergenza di {output_file.stem}.")
        return

    output_file.parent.mkdir(parents=True, exist_ok=True)

    iterations = [s.get('iteration', i) for i, s in enumerate(instance_stats)]
    objective_values = [s.get('lp_solution') for s in instance_stats]
    optimal_value = instance_stats[0].get('optimal_ilp')
    initial_lp_value = instance_stats[0].get('lp_solution')

    if any(v is None for v in objective_values):
        print(f"Dati di soluzione mancanti per {output_file.stem}, grafico non generato.")
        return

    plt.figure(figsize=(12, 7))

    plot_style = 'o' if len(iterations) == 1 else 'o-'
    plt.plot(iterations, objective_values, plot_style, color='b', label='Valore LP con Tagli')

    if initial_lp_value is not None:
        plt.axhline(y=initial_lp_value, color='r', linestyle='--', label=f'LP Iniziale ({initial_lp_value:.2f})')
    if optimal_value is not None:
        plt.axhline(y=optimal_value, color='g', linestyle='--', label=f'Ottimo Intero ({optimal_value:.2f})')

    # Usa il nome pulito per il titolo
    instance_name = clean_instance_name(instance_stats[0].get('instance_name', 'Sconosciuta'))
    title = f'Convergenza Tagli di Gomory - Istanza: {instance_name}'
    if len(iterations) == 1:
        title += "\n(Rilassamento LP Iniziale già Ottimo)"

    plt.title(title)
    plt.xlabel('Numero di Iterazioni di Gomory')
    plt.ylabel('Valore Funzione Obiettivo ')
    plt.gca().xaxis.set_major_locator(plt.MaxNLocator(integer=True))
    plt.legend()
    plt.tight_layout()

    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"Grafico di convergenza per '{instance_name}' salvato in: {output_file}")







def plot_summary_results_category(df: pd.DataFrame, output_dir: Path):
    """
    Crea un grafico a barre che classifica i risultati per ogni istanza.
    """
    df_plot = df.copy()
    df_plot['clean_name'] = df_plot['instance_name'].apply(clean_instance_name)

    category_colors = {
        'LP Ottimo Intero': 'forestgreen',
        'Risolto con Tagli': 'dodgerblue',
        'Limite Raggiunto (Gap Residuo)': 'darkorange',
        'Non Risolto (infeasible)': 'crimson',
        'Errore': 'grey'
    }

    pivot_df = df_plot.pivot_table(index='clean_name', columns='solution_category', aggfunc='size', fill_value=0)

    for cat in category_colors:
        if cat not in pivot_df.columns:
            pivot_df[cat] = 0

    ordered_categories = [cat for cat in category_colors if cat in pivot_df.columns]
    pivot_df = pivot_df[ordered_categories]

    fig, ax = plt.subplots(figsize=(18, 9))
    pivot_df.plot(kind='bar', stacked=True, ax=ax, color=[category_colors.get(cat, 'black') for cat in ordered_categories], width=0.8)

    ax.set_title('Classificazione dei Risultati per Istanza', fontsize=16, fontweight='bold')
    ax.set_xlabel('Istanza del Problema', fontsize=12)
    ax.set_ylabel('Conteggio Istanze (1 per barra)', fontsize=12)
    ax.tick_params(axis='x', rotation=90, labelsize=9)
    ax.legend(title='Categoria Risultato', bbox_to_anchor=(1.02, 1), loc='upper left')
    ax.set_yticks([])

    fig.subplots_adjust(bottom=0.25, right=0.85)
    plot_path = output_dir / "_summary_by_category.png"
    plt.savefig(plot_path, dpi=300)
    plt.close()
    print(f"Grafico riassuntivo per categoria salvato in: {plot_path}")



def plot_gap_closure_efficiency(df: pd.DataFrame, output_dir: Path):
    """
    Crea un grafico a barre divergente per mostrare l'efficienza dei tagli.
    Versione robusta per evitare warning di layout.
    """
    df_plot = df.copy()


    if 'instance_name' not in df_plot.columns:
        print("Errore: la colonna 'instance_name' non è presente nel DataFrame per plot_gap_closure_efficiency.")
        return

    # Escludiamo quelle che erano già ottime e intere al rilassamento LP.
    original_instance_count = len(df_plot)
    df_plot = df_plot[df_plot['solution_category'] != 'LP Ottimo Intero'].copy()

    # Controlla se rimangono dati dopo il filtraggio
    if df_plot.empty:
        print("Nessuna istanza ha richiesto tagli. Il grafico di efficienza del gap non verrà generato.")
        return

    filtered_instance_count = len(df_plot)
    print(f"Info per grafico 'gap_efficiency': Filtrate {original_instance_count - filtered_instance_count} istanze già ottime. Grafico generato su {filtered_instance_count} istanze.")

    df_plot['clean_name'] = df_plot['instance_name'].apply(clean_instance_name)
    df_plot['gap_closure_pct'] = df_plot['gap_closure'] * 100
    df_plot = df_plot.sort_values('gap_closure_pct', ascending=False)

    colors = ['forestgreen' if x >= 0 else 'crimson' for x in df_plot['gap_closure_pct']]

    #altezza dinamica in base al numero di istanze
    num_instances = len(df_plot)
    dynamic_height = max(12, num_instances * 0.35)

    # Creiamo la figura e l'asse esplicitamente per un miglior controllo
    fig, ax = plt.subplots(figsize=(16, dynamic_height))

    ax.barh(df_plot['clean_name'], df_plot['gap_closure_pct'], color=colors)

    current_mode = df_plot['cut_mode'].iloc[0] if not df_plot.empty else ""
    ax.set_title(f'Efficienza dei Tagli ({current_mode}): Chiusura del Gap Relativo', fontsize=16, fontweight='bold')
    ax.set_xlabel('Chiusura del Gap (%) [Positivo = Miglioramento]', fontsize=12)
    ax.set_ylabel('Istanza del Problema', fontsize=12)
    ax.grid(axis='x', linestyle='--', linewidth=0.5)
    ax.axvline(x=0, color='black', linewidth=0.8)

    # Aggiungi etichette sulle barre
    for index, value in enumerate(df_plot['gap_closure_pct']):
        ha = 'left' if value >= 0 else 'right'
        # Aggiustiamo la posizione del testo per non sovrapporsi alle barre
        x_pos = value + (np.sign(value) * 0.5) if value != 0 else 0.5
        ax.text(x_pos, index, f'{value:.2f}%', va='center', ha=ha, fontsize=8)


    fig.subplots_adjust(left=0.3, right=0.95, top=0.95, bottom=0.05)


    plot_path = output_dir / "_gap_efficiency.png"
    plt.savefig(plot_path, dpi=300)
    plt.close(fig) # Chiudiamo la figura esplicitamente
    print(f"Grafico efficienza per modalità '{current_mode}' salvato in: {plot_path}")


def plot_gap_reduction(df: pd.DataFrame, output_dir: Path):
    """Crea il grafico comparativo della riduzione del gap."""
    df_plot = df.copy()
    df_plot['clean_name'] = df_plot['instance_name'].apply(clean_instance_name)
    instance_names = df_plot['clean_name']

    plt.figure(figsize=(18, 9))
    initial_gaps = df_plot['initial_gap'] * 100
    final_gaps = df_plot['final_gap'] * 100

    plt.plot(instance_names, initial_gaps, marker='o', linestyle='--', color='dodgerblue', label='Gap Iniziale (%)')
    plt.plot(instance_names, final_gaps, marker='s', linestyle='-', color='crimson', label='Gap Finale (%)')
    plt.fill_between(instance_names, initial_gaps, final_gaps, where=initial_gaps > final_gaps, color='grey', alpha=0.2, label='Gap Chiuso')

    plt.title('Efficacia dei Tagli di Gomory: Riduzione del Gap Relativo', fontsize=16, fontweight='bold')
    plt.ylabel('Gap Relativo (%)', fontsize=12)
    plt.xlabel('Istanza del Problema', fontsize=12)
    plt.xticks(rotation=90, fontsize=9)
    plt.yticks(fontsize=10)
    plt.legend(fontsize=11)
    plt.grid(True, which='both', linestyle='--', linewidth=0.5)

    plt.subplots_adjust(bottom=0.25)
    gap_plot_path = output_dir / "_comparative_gap_closure.png"
    plt.savefig(gap_plot_path, dpi=300)
    plt.close()
    print(f"Grafico comparativo sulla chiusura del gap salvato in: {gap_plot_path}")


def plot_computational_cost(df: pd.DataFrame, output_dir: Path):
    """Crea il grafico del costo computazionale."""
    df_plot = df.copy()
    df_plot['clean_name'] = df_plot['instance_name'].apply(clean_instance_name)
    instance_names = df_plot['clean_name']
    current_mode = df_plot['cut_mode'].iloc[0] if not df_plot.empty else ""

    fig, ax1 = plt.subplots(figsize=(18, 9))
    color = 'tab:blue'
    ax1.set_xlabel('Istanza del Problema', fontsize=12)
    ax1.set_ylabel('Numero di Iterazioni', color=color, fontsize=12)
    ax1.bar(instance_names, df_plot['total_iterations'], color=color, alpha=0.6, label='Iterazioni')
    ax1.tick_params(axis='y', labelcolor=color)
    ax1.set_xticks(np.arange(len(instance_names)))
    ax1.set_xticklabels(instance_names, rotation=90, ha="center", fontsize=9)

    ax2 = ax1.twinx()
    color = 'tab:red'
    ax2.set_ylabel('Numero Totale di Tagli Aggiunti', color=color, fontsize=12)
    ax2.plot(instance_names, df_plot['total_cuts'], color=color, marker='o', linestyle='--', label='Tagli Totali')
    ax2.tick_params(axis='y', labelcolor=color)

    plt.title('Costo Computazionale dei Tagli di Gomory', fontsize=16, fontweight='bold')
    fig.subplots_adjust(bottom=0.25)
    cost_plot_path = output_dir / "_comparative_computational_cost.png"
    plt.savefig(cost_plot_path, dpi=300)
    plt.close()
    print(f"Grafico comparativo sul costo computazionale per modalità '{current_mode}' salvato in: {cost_plot_path}")



def save_summary_report(all_summaries: list[dict], output_dir: Path):
    """
    Funzione principale che prende i riassunti di tutte le istanze,
    salva un report CSV completo e genera i grafici comparativi.
    """
    if not all_summaries:
        print("Nessun riassunto da elaborare. Nessun report generato.")
        return

    # Preparazione dei Dati e Salvataggio CSV
    df = pd.DataFrame(all_summaries).sort_values('instance_name').reset_index(drop=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    mode_name = df['cut_mode'].iloc[0] if not df.empty else "unknown_mode"
    csv_path = output_dir / f"_summary_{mode_name}.csv"
    df.to_csv(csv_path, index=False, float_format='%.4f')
    print(f"\nReport CSV riassuntivo salvato in: {csv_path}")

    #Generazione di tutti i Grafici Comparativi
    print("\nGenerazione dei grafici riassuntivi...")
    plot_summary_results_category(df, output_dir)
    plot_gap_closure_efficiency(df, output_dir)
    plot_gap_reduction(df, output_dir)
    plot_computational_cost(df, output_dir)

    print("...Grafici generati con successo.")