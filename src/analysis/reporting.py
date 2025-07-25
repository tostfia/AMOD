import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns
from pathlib import Path

from mpl_toolkits.axes_grid1 import make_axes_locatable
from matplotlib.patches import Patch

from config import MAX_ITERATIONS

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

    last_iteration = iterations[-1]
    last_value = objective_values[-1]

    if last_iteration < MAX_ITERATIONS:
        #Crea i punti per la linea orizzontale
        # che va dall'ultimo punto calcolato fino a MAX_ITERATIONS
        line_x = [last_iteration, MAX_ITERATIONS]
        line_y = [last_value, last_value]
        # Disegna la linea orizzontale in blu, senza marcatori, per dare continuità
        plt.plot(line_x, line_y, color='blue', linestyle='-')

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
    out= output_file / f"convergence_{instance_name}.png"
    plt.savefig(out, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"Grafico di convergenza per '{instance_name}' salvato in: {out}")




def plot_cuts_per_iteration(instance_stats: list[dict], output_file: Path):
    """
    Crea un grafico a linee che mostra il numero di tagli aggiunti in ogni specifica iterazione.
    È utile per visualizzare il fenomeno del "tailing-off" (stallo).
    """
    # Controlla se ci sono abbastanza dati per un grafico significativo (almeno un'iterazione con tagli)
    if not instance_stats or len(instance_stats) < 2:
        print(f"Dati insufficienti per il grafico dei tagli per iterazione di {output_file.stem}.")
        return

    output_file.parent.mkdir(parents=True, exist_ok=True)

    # Convertiamo i dati in un DataFrame pandas per calcolare facilmente la differenza
    df = pd.DataFrame(instance_stats)

    # Calcoliamo i tagli aggiunti in QUESTA iterazione, che è la differenza
    # tra il totale tagli di questa riga e quello della riga precedente.
    # Il primo valore (iterazione 0) sarà NaN, che riempiamo correttamente con 0.
    df['cuts_added'] = df['n_cuts'].diff().fillna(0)


    # Creazione del grafico
    plt.figure(figsize=(12, 7))

    # Usiamo un line plot con marcatori per vedere i punti esatti
    plt.plot(df['iterations'], df['cuts_added'], 'o-', color='purple', label='Tagli Aggiunti per Iterazione')

    # Titoli e etichette
    instance_name = clean_instance_name(df['instance_name'].iloc[0])
    plt.title(f'Numero di Tagli Aggiunti per Iterazione - Istanza: {instance_name}')
    plt.xlabel('Numero di Iterazioni di Gomory')
    plt.ylabel('Numero di Tagli Aggiunti')

    # Assicura che gli assi mostrino solo numeri interi
    plt.gca().xaxis.set_major_locator(plt.MaxNLocator(integer=True))
    plt.gca().yaxis.set_major_locator(plt.MaxNLocator(integer=True))

    plt.legend()
    plt.grid(True, linestyle='--')
    plt.tight_layout()

    # Salvataggio del file
    out= output_file / f"cuts_per_iteration_{instance_name}.png"
    plt.savefig(out , dpi=300, bbox_inches='tight')
    plt.close()
    print(f"Grafico dei tagli per iterazione per '{instance_name}' salvato in: {out}")




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
    Versione migliorata con scala percentuale più intuitiva.
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

    # Calcola il gap iniziale assoluto
    df_plot['initial_gap_absolute'] = df_plot['optimal_solution'] - df_plot['initial_lp_solution']

    # Calcola il miglioramento assoluto ottenuto
    df_plot['improvement_absolute'] = df_plot['final_lp_solution'] - df_plot['initial_lp_solution']

    # Calcola la vera percentuale di gap chiuso
    # Gestisce il caso in cui il gap iniziale sia zero per evitare divisioni per zero
    df_plot['gap_closure_pct'] = 0.0
    mask = df_plot['initial_gap_absolute'] > 1e-9 # Evita divisione per zero
    df_plot.loc[mask, 'gap_closure_pct'] = \
        (df_plot.loc[mask, 'improvement_absolute'] / df_plot.loc[mask, 'initial_gap_absolute']) * 100


    df_plot['clean_name'] = df_plot['instance_name'].apply(clean_instance_name)


    # Crea una scala di colori più intuitiva in base alla percentuale
    cmap = plt.cm.RdYlGn  # Red-Yellow-Green colormap
    norm = plt.Normalize(vmin=min(0, df_plot['gap_closure_pct'].min()),
                         vmax=max(100, df_plot['gap_closure_pct'].max()))
    colors = [cmap(norm(x)) for x in df_plot['gap_closure_pct']]

    # Altezza dinamica in base al numero di istanze
    num_instances = len(df_plot)
    dynamic_height = max(12, num_instances * 0.35)

    # Creiamo la figura e l'asse esplicitamente per un miglior controllo
    fig, ax = plt.subplots(figsize=(16, dynamic_height))

    # Crea le barre orizzontali
    bars = ax.barh(df_plot['clean_name'], df_plot['gap_closure_pct'], color=colors)

    # Aggiungi una linea di riferimento a 0%
    ax.axvline(x=0, color='black', linewidth=0.8)

    # Aggiungi linee di riferimento per intervalli significativi
    for x in [25, 50, 75, 100]:
        if x <= max(df_plot['gap_closure_pct'].max(), 100):
            ax.axvline(x=x, color='gray', linestyle=':', alpha=0.6)
            ax.text(x, -0.5, f"{x}%", ha='center', va='top', alpha=0.7)

    current_mode = df_plot['cut_mode'].iloc[0] if not df_plot.empty else ""

    # Titolo e etichette migliorate
    ax.set_title(f'Efficienza dei Tagli ({current_mode}): Chiusura del Gap Relativo', fontsize=16, fontweight='bold')
    ax.set_xlabel('Percentuale di chiusura del gap rispetto al rilassamento LP iniziale', fontsize=12)
    ax.set_ylabel('Istanza del Problema', fontsize=12)

    # Griglia migliorata
    ax.grid(axis='x', linestyle='--', linewidth=0.5)

    # Aggiungi testo esplicativo sulla parte superiore del grafico
    explanation = "100% = Gap completamente chiuso (ottimalità raggiunta)\n0% = Nessun miglioramento dal rilassamento LP"
    ax.text(0.98, 0.98, explanation, transform=ax.transAxes, ha='right', va='top',
            bbox=dict(boxstyle='round,pad=0.5', facecolor='lightyellow', alpha=0.7), fontsize=10)


    # Assicurati che l'asse x mostri valori percentuali con simbolo %
    from matplotlib.ticker import PercentFormatter
    ax.xaxis.set_major_formatter(PercentFormatter())

    ax.set_xlim(0,105)
    # Aggiungi etichette sulle barre
    for bar in bars:
        width = bar.get_width()
        ax.text(width + 1, bar.get_y() + bar.get_height()/2, f'{width:.1f}%', va='center')

    # Adatta il layout per accomodare tutte le etichette
    fig.subplots_adjust(left=0.3, right=0.95, top=0.95, bottom=0.05)

    # Salva il grafico
    plot_path = output_dir / "_gap_efficiency.png"
    plt.savefig(plot_path, dpi=300, bbox_inches='tight')
    plt.close(fig)
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


def plot_combined_summary(csv_path: Path):
    """
    Crea un grafico riassuntivo che mostra le performance combinate
    di tutte le modalità di taglio.
    """
    if not csv_path.exists():
        print(f"Errore: File di riepilogo '{csv_path}' non trovato.")
        return

    df = pd.read_csv(csv_path)

    # --- Analisi dei Dati ---
    # 1. Trova il miglior risultato per ogni istanza
    #    idx = df.groupby('instance_name')['gap_closure'].idxmax()
    #    df_best = df.loc[idx].set_index('instance_name')

    # Un approccio migliore: calcoliamo una categoria combinata
    summary_data = []
    for name, group in df.groupby('instance_name'):
        # Se ALMENO UNA modalità ha risolto l'istanza, è 'Risolto'.
        if 'Risolto con Tagli' in group['solution_category'].values and group['final_gap'].min() < 1e-5:
            category = 'Risolto (da almeno una modalità)'
            # Prendiamo il gap closure della modalità che l'ha risolto
            gap_closure = group[group['solution_category'] == 'Risolto con Tagli']['gap_closure'].iloc[0]
        # Se nessuna l'ha risolta, ma almeno una è LP Ottimo Intero
        elif 'LP Ottimo Intero' in group['solution_category'].values:
            category = 'LP Ottimo Intero'
            gap_closure = 0.0
        # Altrimenti, è 'Limite Raggiunto'. Calcoliamo la MIGLIORE chiusura del gap.
        else:
            category = 'Limite Raggiunto (Miglior Tentativo)'
            gap_closure = group['gap_closure'].max()

        summary_data.append({'instance_name': name, 'category': category, 'best_gap_closure_pct': gap_closure * 100})

    df_summary = pd.DataFrame(summary_data)
    df_summary['clean_name'] = df_summary['instance_name'].apply(clean_instance_name)
    df_summary = df_summary.sort_values('clean_name')

    # --- Creazione del Grafico ---
    fig, ax = plt.subplots(figsize=(24, 12))


    # Categoria 'LP Ottimo Intero'
    subset_green = df_summary[df_summary['category'] == 'LP Ottimo Intero']
    ax.bar(subset_green['clean_name'], [1] * len(subset_green), color='forestgreen', label='LP Ottimo Intero')

    # Categoria 'Risolto'
    subset_blue = df_summary[df_summary['category'] == 'Risolto (da almeno una modalità)']
    ax.bar(subset_blue['clean_name'], [1] * len(subset_blue), color='dodgerblue', label='Risolto (da almeno una modalità)')

    # --- NUOVA LOGICA PER IL "TERMOMETRO" ARANCIONE ---
    subset_orange = df_summary[df_summary['category'] == 'Limite Raggiunto (Miglior Tentativo)']

    cmap = plt.get_cmap('YlOrRd') # Yellow-Orange-Red
    norm = plt.Normalize(vmin=0, vmax=max(1.0, subset_orange['best_gap_closure_pct'].max()))

    for _, row in subset_orange.iterrows():
        gap_pct = row['best_gap_closure_pct']
        # Mappiamo la percentuale a un colore: 0% -> chiaro, 100% -> scuro
        bar_color = cmap(norm(gap_pct))
        ax.bar(row['clean_name'], 1, color=bar_color)

    # Impostazioni del Grafico
    ax.set_title('Efficacia Combinata di Tutti i Metodi di Taglio', fontsize=20, fontweight='bold')
    ax.set_xlabel('Istanza del Problema', fontsize=14)
    ax.set_ylabel('Stato della Soluzione', fontsize=14)
    plt.xticks(rotation=90, fontsize=9)
    ax.set_yticks([]) # Nascondi i tick dell'asse y

    # Crea una legenda combinata
    legend_elements = [Patch(facecolor='forestgreen', label='LP Ottimo Intero'),
                       Patch(facecolor='dodgerblue', label='Risolto (da almeno una modalità)')]
    ax.legend(handles=legend_elements, fontsize=12, title='Categoria Risultato', loc='upper left')

    # Aggiungi una colorbar separata per spiegare il "termometro"
    divider = make_axes_locatable(ax)
    cax = divider.append_axes("right", size="2%", pad=0.1)

    sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
    sm.set_array([]) # Devi passare un array vuoto
    cbar = plt.colorbar(sm, cax=cax)
    cbar.set_label('Percentuale di Gap Chiuso (%) per Istanze Non Risolte', rotation=270, labelpad=20, fontsize=12)


    plt.tight_layout()

    # Salva il grafico
    output_path = Path("results") / "_summary_COMBINED_ANALYSIS.png"
    plt.savefig(output_path, dpi=300)
    plt.close()

    print(f"\nGrafico di analisi combinata salvato in: {output_path}")