from matplotlib import colors
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np

params = {
    'axes.titlesize': 16,
    'axes.labelsize': 12,
    'figure.titleweight':'bold',
    'figure.titlesize':20
}
# Updating the rcParams in Matplotlib
plt.rcParams.update(params)

def get_raw_data():
    df = pd.read_excel('stats.xlsx')
    return df


def get_raw_ratio_data(filename) :
    df = pd.read_csv(filename)
    return df

def gap_variations(df):
    df  = df[["name","relative_gap","ncuts","cluster_type","status","gap"]]
    cluster_types = df["cluster_type"].unique()
    fig, axes = plt.subplots(nrows=2, ncols=2, figsize=(20, 15))
    fig.suptitle("Gap variations over cuts")
    for cluster_name, ax in zip(cluster_types,axes.flatten()):
        cluster_1 = df[(df['cluster_type'] == cluster_name)]
        cluster = cluster_1[cluster_1['status']!="infeasible"]
        for name in cluster["name"].unique():
            instance = cluster[cluster['name'] == name]
            ax.plot(instance["ncuts"].values,instance["gap"].values, label = name)
            ax.set_title(cluster_name)
            ax.set_xlabel("Applied cuts")
            ax.set_ylabel("Gap")
            #ax.set_xlim([0,100])
    plt.legend(title="Instances",loc=3,bbox_to_anchor=(1,0))
    plt.savefig("plots/gap_variations.png")

def gap_histograms(df):
    df  = df[["name","relative_gap","ncuts","cluster_type","status","gap"]]
    cluster_types = df["cluster_type"].unique()
    fig, axes = plt.subplots(nrows=2, ncols=2, figsize=(20, 15))
    fig.suptitle("Relative gap distributions")
    for cluster_name, ax in zip(cluster_types,axes.flatten()):
        cluster_1 = df[(df['cluster_type'] == cluster_name)]
        cluster = cluster_1[cluster_1['status']!="infeasible"]
        N,bins,patches = ax.hist(cluster["relative_gap"].values, label = cluster_name, bins=50, edgecolor = 'black')
        fracs = N / N.max()
        norm = colors.Normalize(fracs.min(), fracs.max())
        for thisfrac, thispatch in zip(fracs, patches):
            color = plt.cm.viridis(norm(thisfrac))
            thispatch.set_facecolor(color)
        ax.set_title(cluster_name)
        ax.set_xlabel("Relative gap")
    plt.savefig("plots/gap_histogram.png")

def gap_variations_over_time(df):
    df  = df[["name","relative_gap","ncuts","cluster_type","elapsed_time","status","gap"]]
    cluster_types = df["cluster_type"].unique()
    fig, axes = plt.subplots(nrows=2, ncols=2, figsize=(20, 15))
    fig.suptitle("Gap variations over time")
    for cluster_name, ax in zip(cluster_types,axes.flatten()):
        cluster_1 = df[(df['cluster_type'] == cluster_name)]
        cluster = cluster_1[cluster_1['status']!="infeasible"]
        for name in cluster["name"].unique():
            instance = cluster[cluster['name'] == name]
            ax.plot((instance["elapsed_time"].sort_values()).values,instance["gap"].values, label = name)
            ax.set_title(cluster_name)
            ax.set_xlabel("Time (ms)")
            ax.set_ylabel("Gap")
            #ax.set_xlim([0,3000])
    plt.legend(title="Instances",loc=3,bbox_to_anchor=(1,0))
    plt.savefig("plots/gap_variations_over_time.png")


def correlation_gap_ratio(df):
    df  = df[["name","relative_gap","ncuts","cluster_type","elapsed_time","status","gap"]]
    cluster_types = df["cluster_type"].unique()
    fig, axes = plt.subplots(nrows=2, ncols=2, figsize=(20, 15))
    fig.suptitle("Gomory effectiveness among profit/weight correlations")
    for cluster_name, ax in zip(cluster_types,axes.flatten()):
        x = []
        y = []
        ratio_df = get_raw_ratio_data("correlations/"+cluster_name+"_corr.csv")
        cluster = df[df['cluster_type'] == cluster_name]
        rel_gap_df = cluster[["name","relative_gap"]]
        for name in cluster["name"].unique():
            gap_instance = rel_gap_df[rel_gap_df['name']==name].min()
            ratio_instance = ratio_df[ratio_df['name']==name]['corr']
            x.append(ratio_instance.values[0])
            y.append(gap_instance.squeeze().values[1])
        ax.scatter(x,y,label = name,alpha=0.5, color ="red")
        ax.set_xlabel("Profit/Weight Correlation")
        ax.set_ylabel("Relative gap")
        ax.set_title(cluster_name)
        ax.set_xlim([-1,1])
    plt.savefig("plots/correlation_gap_ratio.png")



if __name__ == '__main__':
    df = get_raw_data()
    df = df.dropna()
    gap_variations(df)
    gap_histograms(df)
    gap_variations_over_time(df)
    correlation_gap_ratio(df)