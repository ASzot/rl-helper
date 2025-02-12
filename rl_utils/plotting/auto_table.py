import argparse
from typing import Callable, Dict, List, Optional

import numpy as np
import pandas as pd
from omegaconf import OmegaConf

from rl_utils.plotting.utils import MISSING_VALUE
from rl_utils.plotting.wb_query import fetch_data_from_cfg


def plot_table(
    df: pd.DataFrame,
    col_key: str,
    row_key: str,
    cell_key: str,
    col_order: List[str],
    row_order: List[str],
    renames: Optional[Dict[str, str]] = None,
    error_scaling=1.0,
    n_decimals=2,
    missing_fill_value=MISSING_VALUE,
    error_fill_value=0.3444,
    get_row_highlights: Optional[Callable[[str, pd.DataFrame], Optional[str]]] = None,
    get_col_highlights: Optional[Callable[[str, pd.DataFrame], Optional[str]]] = None,
    make_col_header: Optional[Callable[[int], str]] = None,
    x_label: str = "",
    y_label: str = "",
    skip_toprule: bool = False,
    include_err: bool = True,
    write_to=None,
    err_key: Optional[str] = None,
    add_tabular: bool = True,
    add_botrule: bool = False,
    name_bold_fn: Optional[Callable[[str], str]] = None,
    show_row_labels: bool = True,
    show_col_labels: bool = True,
    compute_err_fn: Optional[Callable[[pd.Series], pd.Series]] = None,
    value_scaling: float = 1.0,
    midrule_formatting: str = "\\midrule\n",
    botrule_formatting: str = "\\bottomrule",
    text_columns: Optional[Dict[str, Dict[str, str]]] = None,
    alternating_color_rows: bool = False,
    custom_cell_format_fn: Optional[
        Callable[
            [float, float, str, str],
            str,
        ]
    ] = None,
):
    """
    :param df: The index of the data frame does not matter, only the row values and column names matter.
    :param col_key: A string from the set of columns.
    :param row_key: A string from the set of columns (but this is used to form the rows of the table).
    :param renames: Only used for display name conversions. Does not affect functionality.
    :param row_order: Order of the rows to display. If the value in the row
        order is hline, then a horizontal break is inserted.
    :param make_col_header: Returns the string at the top of the table like
        "ccccc". Put "c|ccccc" to insert a vertical line in between the first
        and other columns.
    :param x_label: Renders another row of text on the top that spans all the columns.
    :param y_label: Renders a side column with vertically rotated text that spawns all the rows.
    :param err_key: If non-None, this will be used as the error and override any error calculation.
    :param show_row_labels: If False, the row names are not diplayed, and no
        column for the row name is displayed.
    :param custom_cell_format_fn: A function that takes as input the cell
        value, standard deviation, the column and row name, and the columns to
        bold their values and returns the latex content that should be
        displayed at that cell.
    :param alternating_color_rows: If True, will color odd rows with `Gray`
        color. You must define this color in your latex doc via
        `definecolor{Gray}{gray}{0.95}`. Note that an `hline` row resets this
        count.

    Example: the data fame might look like
    ```
       democount        type  final_train_success
    0     100  mirl train               0.9800
    1     100  mirl train               0.9900
    3     100   mirl eval               1.0000
    4     100   mirl eval               1.0000
    12     50  mirl train               0.9700
    13     50  mirl train               1.0000
    15     50   mirl eval               1.0000
    16     50   mirl eval               0.7200
    ```
    `col_key='type', row_key='demcount', cell_key='final_train_success'` plots
    the # of demos as rows and the type as columns with the final_train_success
    values as the cell values. Duplicate row and columns are automatically
    grouped together.

    """
    if text_columns is None:
        text_columns = {}
    df[cell_key] = df[cell_key] * value_scaling
    if make_col_header is None:

        def make_col_header(n_cols):
            return "c" * n_cols

    if renames is None:
        renames = {}
    df = df.replace("missing", missing_fill_value)
    df = df.replace("error", error_fill_value)

    rows = {}
    for row_k, row_df in df.groupby(row_key):
        grouped = row_df.groupby(col_key)
        df_avg_y = grouped[cell_key].mean()
        df_std_y = grouped[cell_key].std() * error_scaling

        sel_err = False
        if err_key is not None:
            err = grouped[err_key].mean()
            if not err.hasnans:
                df_std_y = err
                sel_err = True

        if not sel_err and compute_err_fn is not None:
            df_std_y = compute_err_fn(grouped[cell_key])

        rows[row_k] = (df_avg_y, df_std_y)

    col_sep = " & "
    row_sep = " \\\\\n"

    all_s = []

    def clean_text(s):
        return s.replace("%", "\\%").replace("_", " ")

    # Add the column title row.
    row_str = []
    if show_row_labels:
        row_str.append("")
    for col_k in col_order:
        row_str.append("\\textbf{%s}" % clean_text(renames.get(col_k, col_k)))
    all_s.append(col_sep.join(row_str))

    row_index = 0
    for row_k in row_order:
        if row_k == "hline":
            row_index = 0
            all_s.append("\\hline")
            continue
        row_str = []

        if show_row_labels:
            if name_bold_fn is None:
                row_str.append("\\textbf{%s}" % clean_text(renames.get(row_k, row_k)))
            else:
                row_str.append(name_bold_fn(clean_text(renames.get(row_k, row_k))))

        if row_k not in rows:
            print("Could not find ", row_k)
            row_str.extend(["" for _ in col_order])
            all_s.append(col_sep.join(row_str))
            continue
        row_y, row_std = rows[row_k]

        if get_row_highlights is not None:
            sel_cols = get_row_highlights(row_k, row_y)
        elif get_col_highlights is not None:
            all_col_values = {
                col: pd.Series(
                    {
                        row_name: row_y[col]
                        for row_name, (row_y, _) in rows.items()
                        if col in row_y
                    }
                )
                for col in col_order
            }

            sel_cols = []
            for col_k, col_values in all_col_values.items():
                sel_rows_for_col = get_col_highlights(col_k, col_values)
                # If we want to select the current row, add the column to be
                # bolded.
                if row_k in sel_rows_for_col:
                    sel_cols.append(col_k)

        else:
            sel_cols = None

        for col_k in col_order:
            if col_k in text_columns:
                row_str.append(text_columns[col_k].get(row_k, "-"))
            elif col_k not in row_y:
                row_str.append("-")
            else:
                val = row_y.loc[col_k]
                std = row_std.loc[col_k]
                if val == missing_fill_value * value_scaling:
                    row_str.append("-")
                elif val == error_fill_value:
                    row_str.append("E")
                else:
                    if custom_cell_format_fn is None:
                        err = ""
                        if include_err and not np.isnan(std):
                            err = f"$ \\pm$ %.{n_decimals}f " % std
                            err = f"{{\\scriptsize {err} }}"
                        txt = f" %.{n_decimals}f {err}" % val

                        if sel_cols is not None and col_k in sel_cols:
                            txt = "\\textbf{ " + txt + " }"
                    else:
                        txt = custom_cell_format_fn(val, std, col_k, row_k, sel_cols)
                    row_str.append(txt)

        row_index += 1
        row_str = col_sep.join(row_str)
        if row_index % 2 == 0 and alternating_color_rows:
            row_str = "\\rowcolor{Gray} " + row_str
        all_s.append(row_str)

    n_columns = len(col_order)
    if show_row_labels:
        n_columns += 1
    col_header_s = make_col_header(n_columns)
    if y_label != "":
        col_header_s = "c" + col_header_s
        start_of_line = " & "
        toprule = ""

        midrule = "\\cmidrule{2-%s}\n" % (n_columns + 1)
        botrule = midrule
        row_lines = [start_of_line + x for x in all_s[1:]]
        row_lines[0] = (
            "\\multirow{4}{1em}{\\rotatebox{90}{%s}}" % y_label
        ) + row_lines[0]
    else:
        row_lines = all_s[1:]
        start_of_line = ""
        toprule = "\\toprule\n"
        midrule = midrule_formatting
        botrule = botrule_formatting

    if skip_toprule:
        toprule = ""

    if x_label != "":
        toprule += ("& \\multicolumn{%i}{c}{%s}" % (n_columns, x_label)) + row_sep

    ret_s = ""
    if add_tabular:
        ret_s += "\\begin{tabular}{%s}\n" % col_header_s
        # Line above the table.
        ret_s += toprule

    if show_col_labels:
        # Separate the column headers from the rest of the table by a line.
        ret_s += start_of_line + all_s[0] + row_sep
        ret_s += midrule

    all_row_s = ""
    for i, row_line in enumerate(row_lines):
        all_row_s += row_line
        if i == len(row_lines) - 1 and not add_botrule:
            # If we don't add anything at the bottom, we shouldn't add any separator.
            continue

        # Do not add the separator to the last element if we are not in tabular mode.
        if "hline" not in row_line:
            all_row_s += row_sep
        else:
            all_row_s += "\n"

    ret_s += all_row_s
    # Line below the table.
    if add_tabular:
        ret_s += botrule

        ret_s += "\n\\end{tabular}\n"

    if add_botrule:
        ret_s += botrule

    if write_to is not None:
        with open(write_to, "w") as f:
            f.write(ret_s)
        print(f"Wrote result to {write_to}")
    else:
        print(ret_s)

    return ret_s


def plot_from_file(plot_cfg_path, add_query_fields=None):
    cfg = OmegaConf.load(plot_cfg_path)
    df = fetch_data_from_cfg(plot_cfg_path, add_query_fields)

    plot_table(df, cell_key=cfg.plot_key, **cfg.sub_plot_params)
    return df


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--cfg", type=str, required=True)
    args = parser.parse_args()
    plot_from_file(args.cfg)
