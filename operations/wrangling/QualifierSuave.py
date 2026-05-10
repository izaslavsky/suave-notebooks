""" Qualifier Generator and Editor

This script generates qualifiers for the data frame produced
by ZipScript and displays widgets that give users the ability
to edit the qualifiers if needed.

To achieve this functionality, simply run qualifier_editor().

ZipScript must be in the same directory and run prior to
running this script. Please refer to ZipScript for information
on running it.

This script requires that re, pandas, dateutil, requests, and 
panel be installed within the Python environment you are running 
this script on.
"""


# Importing required scripts
import FileScript as fs

# Importing libraries
import re
import pandas as pd
from dateutil.parser import parse
import panel as pn

# Load extensions
pn.extension()


def qualifier_editor():
    """
    Main function
    
    qualifier_editor uses HoloViz to give users the ability 
    to alter data frame qualifiers through the use of widgets.
    Displays the updated data frame when edits are made.
    
    :returns: data frame with qualifiers and editor widgets 
    """ 
    
    # Clears out stored column names if qualifier_editor was previously run.
    if ('stored_quant' in globals()) and ('stored_text' in globals()):
        global stored_quant
        global stored_text
        stored_quant=[]
        stored_text=[]
    
    # Produces data frame with column qualifiers
    df = generate_qualifiers()
    
    # Checks if qualifier_editor was previously run. If so,
    # instantiates previous data frame with new df above.
    if 'updated_df' in globals():
        global updated_df
        updated_df = df
        
    # Column Selector widget
    col_select = pn.widgets.IntSlider(name='Navigate Columns', end=len(df.columns), width=930)
    
    # Variable Selector widget
    var_select = pn.widgets.CrossSelector(options=list(df.columns), height=161)

    # Qualifier Selector widgets
    qualifiers = ['#name', '#img', '#href', '#number', '#link',
                  '#ordinal', '#textlocation', '#multi', '#info', 
                  '#date', '#long', '#hidden', '#hiddenmore']
    qual_select = pn.widgets.Select(name='Select Qualifier(s)', width=112,
                                    margin=(0,0,12,10), options=['None']+qualifiers)
    
    qual_select2 = pn.widgets.Select(width=112, margin=(19,0,12,5), 
                                     options=['#hidden', '#hiddenmore'])
    
    # Qualifier Combination Enabler widget
    combination = pn.widgets.Checkbox(name='Enable Combination', width=150, margin=(-6,0,8,55))
    
    # Rename Column widget
    rename = pn.widgets.TextInput(name = 'Rename Column (Without Qualifier)', 
                                  margin=(-2,0,46,10), width = 230, height=10)

    # Update Data Frame widget
    updater = pn.widgets.Toggle(name='Apply Changes', margin=(8,10,7,10))
    
    # Dictionary to keep track of reserved column names use
    violated = {}
    
    @pn.depends(updater, col_select)
    def update_trigger(update, col=0):
        """
        update_trigger updates the existing data frame
        when there are changes to the update widget or
        the column selector widget.
        
        :param update: bool indicated click on update widget
        :param col: integer representing column to display
        :returns: updated data frame
        """
        
        # Please note: Any function that is dependent on a widgets value 
        # (@pn.depends), like this one, will run every time one of the widget's
        # value is changed. However, this is not limited to a user changing the
        # widgets, but also changed programmatically as well. This is done a
        # few times across this function which leads to redundant calls.
        # These redundant calls can cause problems as they can reassign variables.
        # Hence, you may see some extra variables to detect these redundant calls.
        
        updater.value = False
        
        # Checks for previous runs of this function
        if 'updated_df' not in globals():
            global updated_df
            updated_df = df.copy()
        
        selected = var_select.value.copy()
        
        if len(selected) == 1:
            selected[0] = rename.value
        
        # Removes qualifier from column name if 'None' is
        # selected else concatenates qualifier.
        if qual_select.value == 'None':
            updated = [var.split('#')[0] for var in selected]
            
        # Reserved column names
        elif qual_select.value in ['#name', '#href', '#img']:
            
            # Error message if user attempts to assign reserved column multiple times
            message = '##### '+qual_select.value+' can only be assigned to a single variable.'
            message_widget = pn.Column(message, margin=(0,0,-30,650))
            
            # Cannot assign multiple variables to reserved name
            if (len(selected) > 1):
                return pn.Column(updated_df.iloc[:10, col:col+10], message_widget)
            
            # Cannot reassign reserved name
            elif qual_select.value in violated.keys():
                if violated[qual_select.value] < 2:
                    violated[qual_select.value] +=1
                    return updated_df.iloc[:10, col:col+10]
                else:
                    return pn.Column(updated_df.iloc[:10, col:col+10], message_widget)
            
            col_index = updated_df.columns.get_loc(var_select.value[0])
            updated_df.insert(col_index+1, qual_select.value, updated_df[var_select.value[0]])
            
            var_select.value = []
            violated[qual_select.value] = 1
            
            return updated_df.iloc[:10, col:col+10]
        
        else:
            if combination.value:
                updated = [var.split('#')[0]+qual_select.value+qual_select2.value for var in selected]
            else:
                updated = [var.split('#')[0]+qual_select.value for var in selected]
        
        # Updating stored qualifiers
        global stored_quant
        global stored_text
        stored_quant = pd.Series(stored_quant).replace(var_select.value, updated).tolist()
        stored_text = pd.Series(stored_text).replace(var_select.value, updated).tolist()
        
        # Creates updated variable names
        rename_dict = dict(zip(var_select.value, updated))
        updated_vars = pd.Series(var_select.options).replace(rename_dict).tolist()
        
        # Updates widget values
        var_select.options = updated_vars
        var_select.value = []

        # Renames columns
        updated_df = updated_df.rename(columns=rename_dict)
        
        updater.value = False

        return updated_df.iloc[:10, col:col+10]
    
    @pn.depends(var_select, rename)
    def variable_rename(var, name):
        """
        variable_rename renames variables in a data frame
        when the user does so through a text input widget.
        
        :param var: string, variable to be renamed
        :param name: string, new variable name
        :returns: variable rename widget
        """
        
        # Checks whether variable selector contains a single value.
        # If so, renaming is enabled.
        if len(var_select.value) == 1:
            rename.disabled = False
        else:
            rename.value = ''
            rename.disabled = True
            return
        
        if name == '':
            if len(var) == 0:
                return
            rename.value = var[0].split('#')[0]
            
            
    @pn.depends(combination)
    def combo_trigger(combo):
        """
        combo_trigger enables/disables the second 
        qualifier select widget based on whether
        or not the user wants a qualifier combination
        
        :param bool: bool representing enabling/disabling 
                     second selector widget
        """
        
        if combo:
            qual_select2.disabled = False
        else:
            qual_select2.disabled = True
        

    # Displays widgets produced above
    qualifier_selectors = pn.Row(qual_select, qual_select2)
    right_edit = pn.Column(qualifier_selectors, combination, rename, updater,
                           width=250, css_classes=['widget-box'])
    left_edit = pn.Column(var_select, css_classes=['widget-box'], margin=(0,10,0,0))
    full_edit = pn.Row(left_edit, right_edit, margin=(20,0,0,0))
    full_widget = pn.Column(col_select, pn.panel(update_trigger, width=930), full_edit, pn.panel(variable_rename), pn.panel(combo_trigger), width=930).servable()

    return full_widget


# Store names of numerical and string column types
# as determined by determine_type
quant_cols, text_cols = [], []

# Store names of numerical and string column types
# after quant_cols/text_cols refreshed
stored_quant, stored_text = [], []

def generate_qualifiers():
    """
    Helper function for qualifier_editor
    
    generate_qualifiers produces and applies qualifiers
    to the data frame generated from ZipScript.
    
    :returns: data frame with qualifiers
    """
    
    global stored_quant
    global stored_text
    
    
    # Determines proper data type for each column
    df = fs.final_df.apply(determine_type, axis=0)
    
    num_cols = quant_cols
    str_cols = text_cols
    
    # Checks if column names already contain qualifiers
    qualifiers = ('#name', '#img', '#href', '#number', '#link',
                  '#ordinal', '#textlocation', '#multi', '#info', 
                  '#date', '#long', '#hidden', '#hiddenmore')
    
    for col_name in fs.final_df.columns:
        if col_name.endswith(qualifiers):
            
            for col in fs.final_df.columns:
                # Stores qualifier type for future use
                if col in quant_cols:
                    stored_quant.append(col)
                else:
                    stored_text.append(col) 
                    
            refresh()
                
            return fs.final_df
    
    # Determines proper qualifier for each column
    link_cols = find_cols(df, str_cols, has_link)
    date_cols = find_cols(df, list(set(str_cols).difference(link_cols)), has_date)
    geom_cols = find_cols(df, list(set(str_cols).difference(date_cols)), None)
    long_cols = find_cols(df, list(set(str_cols).difference(geom_cols)), has_long)
    coord_cols = find_cols(df, num_cols, None)
    str_cols = list(set(str_cols).difference(link_cols+date_cols+long_cols+coord_cols))
    num_cols = list(set(num_cols).difference(coord_cols))

    # Applies qualifiers to data frame
    qualifier_dict = {'#number':num_cols, '#link':link_cols, 
                      '#date':date_cols, '#long':long_cols, 
                      '#hiddenmore': geom_cols,'#number#hidden': coord_cols}
    df = add_qualifiers(df, qualifier_dict)
    
    # Stores qualifier type for future use
    for col_name in df.columns:     
        no_qual = col_name.split('#')[0]
        if no_qual in quant_cols:
            stored_quant.append(col_name)
        else:
            stored_text.append(col_name)  
            
    refresh()

    return df

   
def add_qualifiers(df, dic):
    """
    Helper function for generate_qualifiers
    
    add_qualifier generates a new data frame with
    columns renamed to include its respective qualifier.
    
    :param df: data frame
    :param dic: dictionary containing old and new column names
    :returns: data frame with renamed columns
    """
    
    for qualifier in dic.keys():
        with_qualifier = [col + qualifier for col in dic[qualifier]]
        df = df.rename(columns=dict(zip(dic[qualifier], with_qualifier)))
    
    return df


def determine_type(col):
    """
    Helper function for generate_qualifiers
    
    determine_type checks a column to determine the
    most appropriate type of the column (float or string).
    
    :param col: data frame column
    """
    
    for typ in ['float', 'str']:
        try:
            copy = col.copy()
            
            # Checks if values of column are strings of
            # numbers with commas (e.g. '1,629')
            check_num = pd.Series(copy.dropna().unique()).apply(valid_num)
            if check_num.all():
                copy = copy.str.replace(',', '')
            
            # Attempts to convert column type to typ
            converted = copy.dropna().astype(typ)
            copy.loc[converted.index] = converted.values

            if typ == 'float':
                quant_cols.append(col.name)
            elif typ == 'str':
                text_cols.append(col.name)
                
            return copy
        
        except ValueError:
            pass


def valid_num(string):
    """
    Helper function for determine_type
    
    valid_num checks whether a string is in the form
    of a valid number that can be converted to float.
    
    :param string: string
    :returns: bool whether string is a number
    
    :Example:
    >>> valid_num('100,364')
    True
    >>> valid_num('1,3672')
    False
    >>> valid_num('3945')
    True
    """
    
    if type(string) != str:
        return False
    
    # Handles case of decimals
    if '.' in string:
        string = ','.join(string.split('.')[:-1])
    
    # Checks validity of non-character (',', '.') string
    # and characters before the first comma
    new_str = string.split(',')
    if (len(new_str) == 1) and (new_str[0].isdigit()):
        return True
    elif (len(new_str[0]) > 3) or (not new_str[0].isdigit()):
        return False
    
    # Checks that digits after comma are in thousands
    for i in new_str[1:]:
        if (len(i) == 3) and (i.isdigit()):
            continue
        return False
    
    return True


def find_cols(df, cols, col_func=None):
    """
    Helper function for generate_qualifiers
    
    find_cols finds the columns in a data frame
    that satisfy the requirements of a column function.
    
    :param df: data frame
    :param cols: list of column names of df
    :param col_func: function
    :returns: list of column names whos elements satisfy col_func
    """
    
    found = []
    for col in cols:
        
        # When col_func is null, column is categorized solely
        # on its name and not its values.
        if pd.isnull(col_func):
            name = col.lower()
            
            # Uses regex to check for cooordinate columns
            if col in quant_cols:
                rgx_coord = ("(.*[^a-zA-Z0-9]+)?(lon|longitude|" +
                             "lat|latitude)([^a-zA-Z0-9]+.*)?")
                if not pd.isnull(re.fullmatch(rgx_coord, name)):
                    found.append(col)
            
            # Checks for geometry column
            elif 'geometry' in name:
                found.append(col)
                   
            continue
        
        # Checks uniqueness of values when checking for 
        # long qualifier
        elif col_func == has_long:
            num_unique = df[col].nunique()
            
            if num_unique > 200:
                found.append(col)
                continue
        
        # Applies function to unique column values. If every
        # element satisfies the function, the column is stored
        test = pd.Series(df[col].dropna().unique()).apply(col_func)
        if test.all():
            found.append(col)
                         
    return found
        
        
def has_link(string):
    """
    Function passed into find_cols
    
    has_link checks whether a string is 
    in the form of a valid link.
    
    :param string: string
    :returns: bool whether string is a link
    
    :Example:
    >>> has_link('www.google.com')
    True
    >>> has_link('https://www.fda.gov')
    True
    >>> has_link('https://badurl.toolong')
    False
    """
    
    link_regex = ('^(http:\/\/www\.|https:\/\/www\.|http:\/\/|https:\/\/)'+
                 '?[a-z0-9]+([\-\.]{1}[a-z0-9]+)*\.[a-z]{2,5}(:[0-9]{1,5})?(\/.*)?$')
    
    found = re.findall(link_regex, string)
    return len(found) > 0


def has_date(string):
    """
    Function passed into find_cols
    
    has_date checks whether a string is 
    in the form of a valid date.
    
    :param string: string
    :returns: bool whether string is a date
    
    :Example:
    >>> has_date('09/14/1998')
    True
    >>> has_date('1.12.13')
    True
    >>> has_date('1.30')
    False
    """
    
    # Checks whether string has date indicators
    requirement = ['-', '/', ':']
    has_req = [char for char in requirement if char in string]
    if (len(has_req) == 0):
        return False
    
    try: 
        parse(string)
        return True

    except ValueError:
        return False
    
    
def has_long(string):
    """
    Function passed into find_cols
    
    has_long checks whether a string is 
    a long (greater than 100 characters).
    
    :param string: string
    :returns: bool whether string is a long
    """
    
    str_len = len(string)
    return str_len > 100


def refresh():
    """
    refresh clears column names in num_cols
    and text_cols and stores them if needed
    for future use.
    """
    global quant_cols
    quant_cols=[]
    
    global text_cols
    text_cols=[]
