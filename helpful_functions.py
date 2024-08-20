import pandas as pd
import os
import time
import json

brain_api_url = os.environ.get("BRAIN_API_URL", "https://api.worldquantbrain.com")
brain_url = os.environ.get("BRAIN_URL", "https://platform.worldquantbrain.com")

def make_clickable_alpha_id(alpha_id):
    """
    Make alpha_id clickable in dataframes
    So you can go to the platform to analyze simulation result
    """

    url = brain_url + "/alpha/"
    return f'<a href="{url}{alpha_id}">{alpha_id}</a>'


def prettify_result(
    result, detailed_tests_view=False, clickable_alpha_id: bool = False
):
    """
    Combine needed results in one dataframe to analyze your alphas
    Sort by fitness absolute value
    """
    list_of_is_stats = [
        result[x]["is_stats"]
        for x in range(len(result))
        if result[x]["is_stats"] is not None
    ]
    is_stats_df = pd.concat(list_of_is_stats).reset_index(drop=True)
    is_stats_df = is_stats_df.sort_values("fitness", ascending=False)

    expressions = {
        result[x]["alpha_id"]: {"selection": result[x]["simulate_data"]["selection"],
                                "combo": result[x]["simulate_data"]["combo"]}
        if result[x]["simulate_data"]["type"] == "SUPER" 
        else result[x]["simulate_data"]["regular"]
        for x in range(len(result))
        if result[x]["is_stats"] is not None
        }
    expression_df = pd.DataFrame(
        list(expressions.items()), columns=["alpha_id", "expression"]
    )

    list_of_is_tests = [
        result[x]["is_tests"]
        for x in range(len(result))
        if result[x]["is_tests"] is not None
    ]
    is_tests_df = pd.concat(list_of_is_tests, sort=True).reset_index(drop=True)
    is_tests_df = is_tests_df[is_tests_df["result"] != "WARNING"]
    if detailed_tests_view:
        cols = ["limit", "result", "value"]
        is_tests_df["details"] = is_tests_df[cols].to_dict(orient="records")
        is_tests_df = is_tests_df.pivot(
            index="alpha_id", columns="name", values="details"
        ).reset_index()
    else:
        is_tests_df = is_tests_df.pivot(
            index="alpha_id", columns="name", values="result"
        ).reset_index()

    alpha_stats = pd.merge(is_stats_df, expression_df, on="alpha_id")
    alpha_stats = pd.merge(alpha_stats, is_tests_df, on="alpha_id")
    alpha_stats = alpha_stats.drop(
        columns=alpha_stats.columns[(alpha_stats == "PENDING").any()]
    )
    alpha_stats.columns = alpha_stats.columns.str.replace(
        "(?<=[a-z])(?=[A-Z])", "_", regex=True
    ).str.lower()
    if clickable_alpha_id:
        return alpha_stats.style.format({"alpha_id": make_clickable_alpha_id})
    return alpha_stats


def concat_pnl(result):
    """
    Combine needed results in one dataframe to analyze pnls of your alphas
    """
    list_of_pnls = [
        result[x]["pnl"]
        for x in range(len(result))
        if result[x]["pnl"] is not None
    ]
    pnls_df = pd.concat(list_of_pnls).reset_index()

    return pnls_df


def concat_is_tests(result):
    is_tests_list = [
        result[x]["is_tests"]
        for x in range(len(result))
        if result[x]["is_tests"] is not None
    ]
    is_tests_df = pd.concat(is_tests_list, sort=True).reset_index(drop=True)
    return is_tests_df


def save_simulation_result(result):
    """
    Dump simulation result to folder simulation_results
    to json file
    """

    alpha_id = result["id"]
    region = result["settings"]["region"]
    folder_path = "simulation_results/"
    file_path = os.path.join(folder_path, f"{alpha_id}_{region}")

    os.makedirs(folder_path, exist_ok=True)

    with open(file_path, "w") as file:
        json.dump(result, file)

def set_alpha_properties(
    s,
    alpha_id,
    name: str = None,
    color: str = None,
    selection_desc: str = "None",
    combo_desc: str = "None",
    tags: str = ["ace_tag"],
):
    """
    Function changes alpha's description parameters
    """

    params = {
        "color": color,
        "name": name,
        "tags": tags,
        "category": None,
        "regular": {"description": None},
        "combo": {"description": combo_desc},
        "selection": {"description": selection_desc},
    }
    response = s.patch(
        brain_api_url + "/alphas/" + alpha_id, json=params
    )



def save_pnl(pnl_df, alpha_id, region):
    """
    Dump pnl to folder alphas_pnl
    to csv file
    """

    folder_path = "alphas_pnl/"
    file_path = os.path.join(folder_path, f"{alpha_id}_{region}")
    os.makedirs(folder_path, exist_ok=True)

    pnl_df.to_csv(file_path)


def save_yearly_stats(yearly_stats, alpha_id, region):
    """
    Dump yearly-stats to folder yearly_stats
    to csv file
    """

    folder_path = "yearly_stats/"
    file_path = os.path.join(folder_path, f"{alpha_id}_{region}")
    os.makedirs(folder_path, exist_ok=True)    

    yearly_stats.to_csv(file_path, index=False)


def get_alpha_pnl(s, alpha_id):
    """
    Function gets alpha pnl of simulation
    """

    while True:
        result = s.get(
            brain_api_url + "/alphas/" + alpha_id + "/recordsets/pnl"
        )
        if "retry-after" in result.headers:
            time.sleep(float(result.headers["Retry-After"]))
        else:
            break
    pnl = result.json().get("records", 0)
    if pnl == 0:
        return pd.DataFrame()
    if len(pnl[0]) == 2:
        pnl_df = (
            pd.DataFrame(pnl, columns=["Date", "Pnl"])
            .assign(
                alpha_id=alpha_id, Date=lambda x: pd.to_datetime(x.Date, format="%Y-%m-%d")
            )
            .set_index("Date")
        )
    if len(pnl[0]) == 3:
        
        pnl_df = (
            pd.DataFrame(pnl, columns=["Date", "Pnl_combo", "Pnl_eqw"])
            .assign(
                alpha_id=alpha_id, Date=lambda x: pd.to_datetime(x.Date, format="%Y-%m-%d")
            )
            .set_index("Date")
        )
    return pnl_df


def get_alpha_yearly_stats(s, alpha_id):
    """
    Function gets yearly-stats of simulation
    """

    while True:
        result = s.get(
            brain_api_url + "/alphas/"
            + alpha_id
            + "/recordsets/yearly-stats"
        )
        if "retry-after" in result.headers:
            time.sleep(float(result.headers["Retry-After"]))
        else:
            break
    stats = result.json()
    
    if stats.get("records", 0) == 0:
        return pd.DataFrame()
    columns = [dct["name"] for dct in stats["schema"]["properties"]]
    yearly_stats_df = pd.DataFrame(stats["records"], columns=columns).assign(alpha_id=alpha_id)
    return yearly_stats_df

def get_datasets(
    s,
    instrument_type: str = 'EQUITY',
    region: str = 'USA',
    delay: int = 1,
    universe: str = 'TOP3000'
):
    url = brain_api_url + "/data-sets?" +\
        f"instrumentType={instrument_type}&region={region}&delay={str(delay)}&universe={universe}"
    result = s.get(url)
    datasets_df = pd.DataFrame(result.json()['results'])
    return datasets_df


def get_datafields(
    s,
    instrument_type: str = 'EQUITY',
    region: str = 'USA',
    delay: int = 1,
    universe: str = 'TOP3000',
    dataset_id: str = '',
    search: str = ''
):
    if len(search) == 0:
        url_template = brain_api_url + "/data-fields?" +\
            f"&instrumentType={instrument_type}" +\
            f"&region={region}&delay={str(delay)}&universe={universe}&dataset.id={dataset_id}&limit=50" +\
            "&offset={x}"
        count = s.get(url_template.format(x=0)).json()['count'] 
    else:
        url_template = brain_api_url + "/data-fields?" +\
            f"&instrumentType={instrument_type}" +\
            f"&region={region}&delay={str(delay)}&universe={universe}&limit=50" +\
            f"&search={search}" +\
            "&offset={x}"
        count = 100
    
    max_try=5
    datafields_list = []
    for x in range(0, count, 50):
        for _ in range(max_try):
            datafields = s.get(url_template.format(x=x))
            if 'results' in datafields.json():
                break
            else:
                time.sleep(5)
            
        datafields_list.append(datafields.json()['results'])

    datafields_list_flat = [item for sublist in datafields_list for item in sublist]

    datafields_df = pd.DataFrame(datafields_list_flat)
    return datafields_df
