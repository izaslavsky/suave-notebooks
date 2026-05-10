import matplotlib.pyplot as plt 
import panel as pn 
import numpy as np 
import pandas as pd 
import re
pn.extension()

def plot_histogram(df, column, plotting_pane, x_range=None):
    """
    Helper function to plot histogram of a numeric variable
    in the provided x_range onto the panel plotting pane.
    """
    fig, ax = plt.subplots(1,1)
    df[column].plot.hist(bins=50, ax=ax, title = 'Histogram of: ' + column, xlim=x_range)
    ax.set_xlabel(column)
    plotting_pane.object = fig
    plt.close()

def plot_dates(df, plotting_pane, selected_date):
    """
    Plots dates based on slider selection to the plotting pane.
    """
    all_dates = pd.DataFrame(df.to_numpy().flatten(), columns=['date'])
    filtered = all_dates[(all_dates['date'] >= pd.Timestamp(selected_date))]
    if len(filtered) == 0:
        fig, ax = fig, ax = plt.subplots(1,1)
        all_dates.groupby('date').size().plot(kind='bar', ax=ax)
        num = 20
    else:
        fig, ax = fig, ax = plt.subplots(1,1)
        filtered.groupby('date').size().plot(kind='bar', ax=ax)
        if len(filtered.groupby('date').size()) > 20:
            num = int(len(filtered.groupby('date').size())/15)
        else:
            num = 1
    ax.set_xticks(ax.get_xticks()[::num])
    ax.set_ylabel('Frequency')
    for tick in ax.get_xticklabels():
        tick.set_rotation(70)
    plotting_pane.object = fig
    plt.close()

def find_unique(df, var):
    """
    Helper function to return all unique entries for #multi survey variables
    """
    arr = df[var].unique()
    all_entries = set()
    for i in range(len(arr)):
        if arr[i] != arr[i]:
            continue
        if (i != 0) and ('|' in arr[i]):
            arr[i] = arr[i].split('|')
            for j in arr[i]:
                all_entries.add(j)
        else:
            all_entries.add(arr[i])
    all_entries = list(all_entries)
    return all_entries

def find_tags(value):
    """
    Helper function to extract SuAVE qualifiers from variable names
    """
    tags = re.findall('#\S+', value)
    if tags == []:
        return ['untagged']
    return tags

def get_factors(df):
    """
    Helper function to collect all variables and their respective levels from the 
    input survey and outputs a resulting array containing all variables + levels.
    """
    out = np.array([])
    for f in list(df.columns):
        if '#multi' in f:
            levels = find_unique(df, f)
        else:
            levels = df[f].value_counts().index.to_list()
        levels = [str(f) + '_' + str(i) for i in levels]
        out = np.append(out, levels)
    return out

def convert_factor(variable, input_level):
    """
    Helper function to convert a string interval
    into a pandas interval type
    """
    tag = variable.split('#')[1]
    if tag == 'number':
        left, right = [i.strip('[]() ') for i in input_level.split(',')]
        return pd.Interval(round(float(left), 3), round(float(right), 3), closed='left')
    elif tag == 'date':
        left, right = [i.strip('[]() ') for i in input_level.split(',')]
        return pd.Interval(pd.Timestamp(left), pd.Timestamp(right), closed='left')

def find_factor_contributions(df, selected_var, selected_level, var_levels):
    """
    Helper function to find all the factor contributions at the level of the variable of interest. 
    """
    tag = selected_var.split('#')[1]
    if tag == 'number' or tag == 'date':
        selected_level = convert_factor(selected_var, selected_level)

    x_count = df[df[selected_var]==selected_level].shape[0]    
    x_prop = df[df[selected_var]==selected_level].shape[0]/df.shape[0]
    out_dict = dict()
    for level in var_levels:
        var, factor = level.split('_')
        level_tag = var.split('#')[1]
        if level_tag == 'number' or level_tag == 'date':
            factor = convert_factor(var, factor)


        a_count = df[df[var]==factor].shape[0]
        ax_count = df[(df[var]==factor) & (df[selected_var]==selected_level)].shape[0]
        try:
            ax_prop = ax_count/a_count
            completeness = round((ax_count/x_count)*100, 3)
        except:
            ax_prop = 0
            completeness = 0
        contribution = round((ax_prop - x_prop)*100, 3)
        accuracy = round(ax_prop*100, 3)
        value_name = level.split('#')[0] + ': ' + str(factor)
        selected_name = selected_var.split('#')[0] + ': ' + str(selected_level)
        if selected_name == value_name:
            continue
        out_dict[value_name] = [accuracy,completeness,contribution,a_count,ax_count,find_tags(var)]
    return out_dict

def color(val):
    """
    Syling function to change color of scalar values
    """
    color = 'red' if val < 0 else 'green'
    return 'color: %s' % color

def filter_counts(df):
    """
    Helper function to remove 0 counts from output dataframe
    """
    df = df[df['Completeness'] > 0]
    return df

def search_filter(df, pattern, column):
    """
    Helper function to filter dataframe values from text input
    """
    if not pattern:
        return df
    return df[df[column].str.contains(pattern, case=False)]

def build_df(contribution_dict):
    """
    Helper function to build the output dataframe from the dictionary
    of factor contributions
    """
    out = pd.DataFrame.from_dict(contribution_dict).T.reset_index()
    out.columns = ['Potential Explanatory Values (X)',
                   'Accuracy',
                   'Completeness',
                   'Contribution of A',
                   'Count (A)',
                   'Count (AX)',
                   'SuAVE Qualifiers']
    out['SuAVE Qualifiers'] = out['SuAVE Qualifiers'].apply(lambda x: x[0])
    out['SuAVE Qualifiers'] = out['SuAVE Qualifiers'].apply(lambda x: 'categorical' if x not in ['#number', '#date'] else x)
    return out

def build_table(df):
    """
    Helper function to build the output display table and define filtering
    widgets for respective columns.
    """
    # create output table for display
    tab = pn.widgets.Tabulator(filter_counts(df), pagination='remote',
                               show_index=False, hidden_columns=['SuAVE Qualifiers'])
    tab.style.applymap(color, subset=pd.IndexSlice[:, ['Contribution of A']])
    # define filtering widgets
    checkbox = pn.widgets.CheckBoxGroup(options=['#number','#date','categorical'], value=['categorical'], width=200, inline=True)
    contribution_slider = pn.widgets.RangeSlider(start=-100, end=100, name='Contribution Filter', width=175)
    completeness_slider = pn.widgets.RangeSlider(start=0, end=100, name='Completeness Filter', width=175)
    accuracy_slider = pn.widgets.RangeSlider(start=0, end=100, name='Accuracy Filter', width=175)
    count_slider = pn.widgets.RangeSlider(start=0, end=df['Count (AX)'].max(), name='Count (AX) Filter', width=175)
    search = pn.widgets.TextInput(name='Search Explanatory Values', placeholder='Enter text to filter values', width=175)
    # apply filtering widgets to respective table columns
    tab.add_filter(checkbox, 'SuAVE Qualifiers')
    tab.add_filter(contribution_slider, 'Contribution of A')
    tab.add_filter(completeness_slider, 'Completeness')
    tab.add_filter(accuracy_slider, 'Accuracy')
    tab.add_filter(count_slider, 'Count (AX)')
    tab.add_filter(pn.bind(search_filter, pattern=search, column='Potential Explanatory Values (X)'))
    return search, checkbox, accuracy_slider, completeness_slider, contribution_slider, count_slider, tab