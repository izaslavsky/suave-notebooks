import pandas as pd
import panel as pn
def slider(data):
    """
    slider creates an interactive display of a
    data frame.
    
    :param df: data frame
    :returns: interactive dataframe
    """
    
    ## Row Selector widget
    row_selection = pn.widgets.IntSlider(name='Navigate Rows', width=350, 
                                         margin=(0,50,-15,0), end=len(data)-1)

    # Column Selector widget
    col_selection = pn.widgets.IntSlider(name='Navigate Columns', width=350, 
                                         margin=(0,0,5,0), end=len(data.columns))
    
    @pn.depends(row_selection, col_selection)
    def navigate_data(row, col):
        return data.iloc[row:row+5, col:col+7]
    

    return pn.Column(pn.Row(row_selection, col_selection), pn.panel(navigate_data, width=800), width=800).servable()



def extract_data(path):
    """
    extract_data reads files from various formats
    
    :param link: string representing path to file
    :returns: data frame of file
    """

    # Reading file at path
    if path.endswith(('.txt', 'tsv')):
        try:
            data = pd.read_csv(path, sep='\t', encoding="latin-1")
        except UnicodeDecodeError:
            data = pd.read_csv(path, sep='\t', encoding="ISO-8859-1")
    elif path.endswith('.csv'):
        try:
            data = pd.read_csv(path, encoding="latin-1")
        except UnicodeDecodeError:
            data = pd.read_csv(path, encoding="ISO-8859-1")
    else:
        return None
    
    cleaned_data = (data
                    .dropna(axis=1, how='all')
                    .dropna(axis=0, how='all'))
    
    return cleaned_data
