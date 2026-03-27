from pathlib import Path
import html
import re

import folium
import geopandas as gpd
import pandas as pd
from branca.colormap import linear
from folium.features import DivIcon


ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "dati_elezioni"
GEO_DIR = ROOT / "geoframes"
DOCS_DIR = ROOT / "docs"
MAPS_DIR = DOCS_DIR / "maps"
DATA_OUT_DIR = DOCS_DIR / "data"

MAPS_DIR.mkdir(parents=True, exist_ok=True)
DATA_OUT_DIR.mkdir(parents=True, exist_ok=True)

PD_2021 = "PD PARTITO DEMOCRATICO"
ROMA_FUTURA_2021 = "ROMA FUTURA FEMMINISTA EGUALITARIA ECOLOGISTA"

PARTY_CONFIGS = [
    {
        "key": "pd",
        "label": "PD",
        "list_name": PD_2021,
        "color": "#b42318",
        "show": True,
    },
    {
        "key": "roma_futura",
        "label": "Roma Futura",
        "list_name": ROMA_FUTURA_2021,
        "color": "#d97706",
        "show": False,
    },
]


def normalize_sections(df: pd.DataFrame, column: str = "SEZIONE") -> pd.DataFrame:
    out = df.copy()
    out[column] = pd.to_numeric(out[column], errors="coerce")
    out = out.dropna(subset=[column])
    out[column] = out[column].astype(int)
    return out


def clean_match_quartieri(df: pd.DataFrame) -> pd.DataFrame:
    cols = [c for c in df.columns if not str(c).startswith("Unnamed") and c != "H1"]
    out = df[cols].copy()
    out = normalize_sections(out)
    out["COD_ASC"] = out["COD_ASC"].astype(str)
    out["NOME_QUARTIERE"] = out["NOME_QUARTIERE"].astype(str)
    return out[["SEZIONE", "COD_ASC", "NOME_QUARTIERE"]].drop_duplicates()


def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def surname_only(full_name: str) -> str:
    if not isinstance(full_name, str):
        return ""
    parts = [p for p in full_name.strip().split() if p]
    return parts[-1] if parts else full_name


def build_top10_per_section(preferences: pd.DataFrame, list_name: str, output_col: str) -> pd.DataFrame:
    filtered = preferences.loc[preferences["LISTA"] == list_name].copy()
    filtered["PREFERENZE"] = pd.to_numeric(filtered["PREFERENZE"], errors="coerce").fillna(0)
    grouped = (
        filtered.groupby(["SEZIONE", "CANDIDATO"], as_index=False)["PREFERENZE"]
        .sum()
        .sort_values(["SEZIONE", "PREFERENZE", "CANDIDATO"], ascending=[True, False, True])
    )
    top10 = grouped.groupby("SEZIONE").head(10).copy()
    top10["rank"] = top10.groupby("SEZIONE").cumcount() + 1
    top10["row"] = (
        top10["rank"].astype(str)
        + ". "
        + top10["CANDIDATO"]
        + " ("
        + top10["PREFERENZE"].round(0).astype(int).astype(str)
        + ")"
    )
    return top10.groupby("SEZIONE")["row"].apply(" | ".join).reset_index(name=output_col)


def build_coalition_frame(
    lists_df: pd.DataFrame,
    precincts: gpd.GeoDataFrame,
    preferences_df: pd.DataFrame,
    party_configs: list[dict],
) -> gpd.GeoDataFrame:
    cols = ["SEZIONE", "TOTALE", "AFFLUENZA"] + [cfg["list_name"] for cfg in party_configs]
    out = lists_df[cols].copy()
    out = out.rename(columns={"TOTALE": "totale_lista", "AFFLUENZA": "affluenza"})

    vote_cols = []
    for cfg in party_configs:
        vote_col = f"{cfg['key']}_votes"
        out[vote_col] = pd.to_numeric(out[cfg["list_name"]], errors="coerce").fillna(0)
        vote_cols.append(vote_col)
        out = out.drop(columns=[cfg["list_name"]])

    out["coalition_votes"] = out[vote_cols].sum(axis=1)
    out["coalition_share"] = out["coalition_votes"] / out["totale_lista"]
    out["Quota coalizione sinistra"] = out["coalition_share"]

    for cfg in party_configs:
        top_col = f"top10_{cfg['key']}"
        top_df = build_top10_per_section(preferences_df, cfg["list_name"], top_col)
        out = out.merge(top_df, on="SEZIONE", how="left")

    return precincts.merge(out, on="SEZIONE", how="inner")


def build_popup_frame(df: gpd.GeoDataFrame, tipo_label: str, party_configs: list[dict]) -> gpd.GeoDataFrame:
    out = df.copy()
    out["Percentuale coalizione sinistra"] = (out["coalition_share"].fillna(0) * 100).round(2).astype(str) + "%"
    out["Voti coalizione sinistra"] = out["coalition_votes"].fillna(0).round(0).astype(int)
    out["Affluenza"] = (out["affluenza"].fillna(0) * 100).round(2).astype(str) + "%"
    out["Tipo elezione"] = tipo_label

    for cfg in party_configs:
        vote_col = f"{cfg['key']}_votes"
        out[f"Voti {cfg['label']}"] = out[vote_col].fillna(0).round(0).astype(int)
        top_col = f"top10_{cfg['key']}"
        out[f"Top 10 preferenze {cfg['label']}"] = (
            out[top_col]
            .fillna("Dato non disponibile")
            .astype(str)
            .str.replace(" | ", "\n", regex=False)
        )

    keep_cols = [
        "SEZIONE",
        "geometry",
        "Percentuale coalizione sinistra",
        "Voti coalizione sinistra",
        "Affluenza",
        "Tipo elezione",
    ]
    for cfg in party_configs:
        keep_cols.append(f"Voti {cfg['label']}")
    for cfg in party_configs:
        keep_cols.append(f"Top 10 preferenze {cfg['label']}")
    return out[keep_cols].copy()


def add_map_theme(map_obj: folium.Map) -> None:
    theme = """
    <style>
      .leaflet-container {
        background:
          radial-gradient(circle at top left, rgba(8, 145, 178, 0.10), transparent 34%),
          radial-gradient(circle at top right, rgba(245, 158, 11, 0.08), transparent 24%),
          linear-gradient(180deg, #fffdf8, #f6fbff);
      }
      .leaflet-control-layers,
      .leaflet-popup-content-wrapper,
      .leaflet-popup-tip,
      .info.legend {
        background: rgba(255, 253, 248, 0.95) !important;
        border: 1px solid rgba(8, 145, 178, 0.15);
        box-shadow: 0 18px 40px rgba(31, 41, 55, 0.14);
      }
      .leaflet-control-layers {
        border-radius: 16px !important;
        padding: 4px 6px;
      }
      .leaflet-control-layers label {
        color: #183b4d;
      }
      .leaflet-popup-content {
        color: #213547;
        line-height: 1.45;
      }
      .foliumpopup td {
        white-space: pre-line;
        max-width: 320px;
      }
      .foliumpopup tr:nth-child(8) th,
      .foliumpopup tr:nth-child(8) td {
        color: #b42318;
      }
      .foliumpopup tr:nth-child(9) th,
      .foliumpopup tr:nth-child(9) td {
        color: #d97706;
      }
      .info.legend {
        color: #183b4d !important;
        border-radius: 16px !important;
      }
    </style>
    """
    map_obj.get_root().html.add_child(folium.Element(theme))


def add_title_box(map_obj: folium.Map, title: str, subtitle: str) -> None:
    box = f"""
    <div style='position: fixed; z-index: 9999; left: 50%; top: 16px; transform: translateX(-50%); width: min(560px, calc(100% - 36px)); background: linear-gradient(180deg, rgba(255,253,248,0.96), rgba(245,250,255,0.93)); border: 1px solid rgba(8,145,178,0.18); border-radius: 18px; padding: 10px 14px; box-shadow: 0 18px 42px rgba(31,41,55,0.16); font-family: Segoe UI, Arial, sans-serif; text-align: center;'>
      <div style='font-size: 15px; font-weight: 700; color: #183b4d; margin-bottom: 4px;'>{html.escape(title)}</div>
      <div style='font-size: 11px; line-height: 1.35; color: #35566a;'>{html.escape(subtitle)}</div>
    </div>
    """
    map_obj.get_root().html.add_child(folium.Element(box))


def compute_quartiere_strength(
    preferences: pd.DataFrame,
    match_quartieri: pd.DataFrame,
    quartieri_geom: gpd.GeoDataFrame,
    list_name: str,
) -> gpd.GeoDataFrame:
    filtered = preferences.loc[preferences["LISTA"] == list_name].copy()
    filtered["PREFERENZE"] = pd.to_numeric(filtered["PREFERENZE"], errors="coerce").fillna(0)
    merged = filtered.merge(match_quartieri, on="SEZIONE", how="inner")
    by_quartiere_candidate = (
        merged.groupby(["COD_ASC", "NOME_QUARTIERE", "CANDIDATO"], as_index=False)["PREFERENZE"]
        .sum()
        .sort_values(["COD_ASC", "PREFERENZE", "CANDIDATO"], ascending=[True, False, True])
    )
    top5 = by_quartiere_candidate.groupby("COD_ASC").head(5).copy()
    top5["label_name"] = (
        top5["CANDIDATO"].apply(surname_only)
        + " ("
        + top5["PREFERENZE"].round(0).astype(int).astype(str)
        + ")"
    )

    pairs = (
        top5.groupby("COD_ASC")[["label_name", "PREFERENZE"]]
        .apply(lambda grp: list(zip(grp["label_name"], grp["PREFERENZE"])))
        .reset_index(name="top_candidates_quartiere")
    )
    quartieri = quartieri_geom.merge(pairs, on="COD_ASC", how="left")
    quartieri["top_candidates_quartiere"] = quartieri["top_candidates_quartiere"].apply(
        lambda value: value if isinstance(value, list) else []
    )
    quartieri["label_point"] = quartieri.representative_point()
    return quartieri


def add_quartieri_zoom_labels(
    map_obj: folium.Map,
    quartieri_gdf: gpd.GeoDataFrame,
    layer_name: str,
    color: str,
    show: bool,
) -> None:
    layer_slug = slugify(layer_name)
    layer = folium.FeatureGroup(name=layer_name, show=show)

    for _, row in quartieri_gdf.iterrows():
        entries = row.get("top_candidates_quartiere", [])
        if not entries:
            continue

        point = row["label_point"]
        quartiere = html.escape(str(row["DEN_Z_URB"]))
        spans = []

        for idx, (label, votes) in enumerate(entries, start=1):
            if votes <= 0:
                continue
            size = 16 if idx == 1 else (14 if idx == 2 else (12 if idx == 3 else (11 if idx == 4 else 10)))
            css_class = f"{layer_slug}-word {layer_slug}-word-{idx}"
            spans.append(
                f"<span class='{css_class}' style='font-size:{size}px; font-weight:700; color:{color}; opacity:0.72; display:inline-block; margin:0 4px 2px; text-shadow:0 1px 0 rgba(255,255,255,0.75);'>"
                f"{html.escape(label)}</span>"
            )

        if not spans:
            continue

        block = f"""
        <div style='width:240px; text-align:center; transform: translate(-120px, -8px); font-family: Segoe UI, Arial, sans-serif;'>
          <div style='font-size:10px; letter-spacing:0.1em; text-transform:uppercase; color:#48606f; opacity:0.52; margin-bottom:3px;'>{quartiere}</div>
          <div>{''.join(spans)}</div>
        </div>
        """
        folium.Marker(location=[point.y, point.x], icon=DivIcon(html=block)).add_to(layer)

    layer.add_to(map_obj)

    map_name = map_obj.get_name()
    js = f"""
    <script>
    function updateQuartiereWords_{map_name}_{layer_slug}() {{
      var zoom = {map_name}.getZoom();
      document.querySelectorAll('.{layer_slug}-word-1').forEach(function(el) {{ el.style.display = ''; }});
      document.querySelectorAll('.{layer_slug}-word-2').forEach(function(el) {{ el.style.display = zoom >= 11 ? '' : 'none'; }});
      document.querySelectorAll('.{layer_slug}-word-3').forEach(function(el) {{ el.style.display = zoom >= 12 ? '' : 'none'; }});
      document.querySelectorAll('.{layer_slug}-word-4').forEach(function(el) {{ el.style.display = zoom >= 13 ? '' : 'none'; }});
      document.querySelectorAll('.{layer_slug}-word-5').forEach(function(el) {{ el.style.display = zoom >= 14 ? '' : 'none'; }});
    }}
    {map_name}.whenReady(function() {{
      updateQuartiereWords_{map_name}_{layer_slug}();
      {map_name}.on('zoomend', updateQuartiereWords_{map_name}_{layer_slug});
    }});
    </script>
    """
    map_obj.get_root().html.add_child(folium.Element(js))


def save_map(
    gdf: gpd.GeoDataFrame,
    quartieri_layers: list[tuple[gpd.GeoDataFrame, dict]],
    output_name: str,
    title: str,
    subtitle: str,
    popup_tipo_label: str,
    party_configs: list[dict],
) -> Path:
    popup_gdf = build_popup_frame(gdf, tipo_label=popup_tipo_label, party_configs=party_configs)
    popup_gdf["share_value"] = gdf["coalition_share"].fillna(0).to_numpy()
    share_min = float(popup_gdf["share_value"].min())
    share_max = float(popup_gdf["share_value"].max())
    if share_min == share_max:
        share_max = share_min + 1e-9
    colormap = linear.YlGnBu_09.scale(share_min, share_max)
    popup_gdf["fill_color"] = popup_gdf["share_value"].apply(colormap)

    popup_fields = [
        "SEZIONE",
        "Tipo elezione",
        "Percentuale coalizione sinistra",
        "Voti coalizione sinistra",
        "Affluenza",
    ]
    popup_aliases = [
        "Sezione",
        "Tipo elezione",
        "Percentuale coalizione sinistra",
        "Voti coalizione sinistra",
        "Affluenza",
    ]

    for cfg in party_configs:
        popup_fields.append(f"Voti {cfg['label']}")
        popup_aliases.append(f"Voti {cfg['label']}")
    for cfg in party_configs:
        popup_fields.append(f"Top 10 preferenze {cfg['label']}")
        popup_aliases.append(f"Top 10 preferenze {cfg['label']}")

    union_geom = gdf.geometry.union_all()
    center = [float(union_geom.centroid.y), float(union_geom.centroid.x)]
    m = folium.Map(location=center, zoom_start=11, tiles="CartoDB positron", control_scale=True)
    minx, miny, maxx, maxy = gdf.total_bounds
    m.fit_bounds([[float(miny), float(minx)], [float(maxy), float(maxx)]])
    map_name = m.get_name()
    zoom_js = f"""
    <script>
      {map_name}.whenReady(function() {{
        {map_name}.setZoom({map_name}.getZoom() + 1);
      }});
    </script>
    """
    m.get_root().html.add_child(folium.Element(zoom_js))

    geojson = folium.GeoJson(
        data=popup_gdf.to_json(),
        name="Quota coalizione sinistra",
        style_function=lambda feature: {
            "fillColor": feature["properties"]["fill_color"],
            "color": "#35566a",
            "weight": 0.12,
            "fillOpacity": 0.78,
        },
        highlight_function=lambda feature: {
            "fillColor": feature["properties"]["fill_color"],
            "color": "#0f3d56",
            "weight": 0.8,
            "fillOpacity": 0.88,
        },
        tooltip=folium.GeoJsonTooltip(
            fields=["SEZIONE", "Percentuale coalizione sinistra", "Voti coalizione sinistra"],
            aliases=["Sezione", "Percentuale coalizione sinistra", "Voti coalizione sinistra"],
            localize=True,
            sticky=False,
            labels=True,
        ),
        popup=folium.GeoJsonPopup(
            fields=popup_fields,
            aliases=popup_aliases,
            localize=True,
            labels=True,
            sticky=False,
        ),
    )
    geojson.add_to(m)

    add_map_theme(m)
    for quartieri_layer, cfg in quartieri_layers:
        add_quartieri_zoom_labels(
            map_obj=m,
            quartieri_gdf=quartieri_layer,
            layer_name=f"Preferenze {cfg['label']}",
            color=cfg["color"],
            show=cfg["show"],
        )
    add_title_box(m, title, subtitle)
    colormap.caption = "Quota coalizione sinistra"
    colormap.add_to(m)
    folium.LayerControl(collapsed=False).add_to(m)

    output_path = MAPS_DIR / output_name
    m.save(output_path)
    return output_path


def build_quartieri_layers(
    preferences_df: pd.DataFrame,
    match_quartieri: pd.DataFrame,
    quartieri_geom: gpd.GeoDataFrame,
    party_configs: list[dict],
) -> list[tuple[gpd.GeoDataFrame, dict]]:
    layers = []
    for cfg in party_configs:
        quartieri = compute_quartiere_strength(
            preferences=preferences_df,
            match_quartieri=match_quartieri,
            quartieri_geom=quartieri_geom,
            list_name=cfg["list_name"],
        )
        layers.append((quartieri, cfg))
    return layers


def build_summary(df: gpd.GeoDataFrame, party_configs: list[dict], tipo: str) -> pd.DataFrame:
    cols = ["SEZIONE", "coalition_votes", "coalition_share"]
    for cfg in party_configs:
        cols.extend([f"{cfg['key']}_votes", f"top10_{cfg['key']}"])
    out = df[cols].copy()
    out["tipo"] = tipo
    return out


def main() -> None:
    print("Loading source data...", flush=True)
    precincts = normalize_sections(gpd.read_file(GEO_DIR / "precincts_roma_bulding.geojson"))[
        ["SEZIONE", "geometry"]
    ]
    quartieri_geom = gpd.read_file(GEO_DIR / "roma_quartieri.geojson")[
        ["COD_ASC", "DEN_Z_URB", "geometry"]
    ].copy()
    match_quartieri = clean_match_quartieri(pd.read_csv(GEO_DIR / "roma_match_quartieri.csv"))

    liste_comune_2021 = normalize_sections(pd.read_csv(DATA_DIR / "comunali_sindaco_lista_2021.csv"))
    preferenze_comune_2021 = normalize_sections(pd.read_csv(DATA_DIR / "comunali_preferenze_2021.csv"))

    liste_municipio3_2021 = normalize_sections(pd.read_csv(DATA_DIR / "comunali_liste_municipio_3_2021.csv"))
    preferenze_municipio3_2021 = normalize_sections(
        pd.read_csv(DATA_DIR / "comunali_preferenze_2021_municipio_3_2021.csv")
    )

    print("Building coalition frames...", flush=True)
    mappa_comune = build_coalition_frame(
        lists_df=liste_comune_2021,
        precincts=precincts,
        preferences_df=preferenze_comune_2021,
        party_configs=PARTY_CONFIGS,
    )

    mun3_sections = set(liste_municipio3_2021["SEZIONE"].unique())
    mappa_comune_mun3 = mappa_comune.loc[mappa_comune["SEZIONE"].isin(mun3_sections)].copy()

    mappa_municipio = build_coalition_frame(
        lists_df=liste_municipio3_2021,
        precincts=precincts,
        preferences_df=preferenze_municipio3_2021,
        party_configs=PARTY_CONFIGS,
    )

    print("Building preference layers...", flush=True)
    quartieri_comune = build_quartieri_layers(
        preferences_df=preferenze_comune_2021,
        match_quartieri=match_quartieri,
        quartieri_geom=quartieri_geom,
        party_configs=PARTY_CONFIGS,
    )

    codici_mun3 = match_quartieri.loc[match_quartieri["SEZIONE"].isin(mun3_sections), "COD_ASC"].unique()
    quartieri_mun3_comune = [
        (gdf.loc[gdf["COD_ASC"].isin(codici_mun3)].copy(), cfg) for gdf, cfg in quartieri_comune
    ]
    quartieri_mun3_municipio = [
        (
            compute_quartiere_strength(
                preferences=preferenze_municipio3_2021,
                match_quartieri=match_quartieri.loc[match_quartieri["SEZIONE"].isin(mun3_sections)],
                quartieri_geom=quartieri_geom,
                list_name=cfg["list_name"],
            ).loc[lambda frame: frame["COD_ASC"].isin(codici_mun3)].copy(),
            cfg,
        )
        for cfg in PARTY_CONFIGS
    ]

    print("Saving Roma map...", flush=True)
    save_map(
        gdf=mappa_comune,
        quartieri_layers=quartieri_comune,
        output_name="roma_pd_comune_2021.html",
        title="Percentuale di voti alle liste e preferenze",
        subtitle="Per selezionare le preferenze di lista utilizza il menu a destra.",
        popup_tipo_label="Elezione comunale 2021",
        party_configs=PARTY_CONFIGS,
    )

    print("Saving Municipio III comune map...", flush=True)
    save_map(
        gdf=mappa_comune_mun3,
        quartieri_layers=quartieri_mun3_comune,
        output_name="municipio3_pd_comune_2021.html",
        title="Percentuale di voti alle liste e preferenze",
        subtitle="Per selezionare le preferenze di lista utilizza il menu a destra.",
        popup_tipo_label="Elezione comunale 2021",
        party_configs=PARTY_CONFIGS,
    )

    print("Saving Municipio III municipio map...", flush=True)
    save_map(
        gdf=mappa_municipio,
        quartieri_layers=quartieri_mun3_municipio,
        output_name="municipio3_pd_municipio_2021.html",
        title="Percentuale di voti alle liste e preferenze",
        subtitle="Per selezionare le preferenze di lista utilizza il menu a destra.",
        popup_tipo_label="Elezione municipale 2021",
        party_configs=PARTY_CONFIGS,
    )

    print("Writing summary CSVs...", flush=True)
    summary_comune = build_summary(mappa_comune, PARTY_CONFIGS, "comune_2021")
    summary_municipio = build_summary(mappa_municipio, PARTY_CONFIGS, "municipio3_2021")

    summary_comune.to_csv(DATA_OUT_DIR / "coalizione_sinistra_section_summary_comune_2021.csv", index=False)
    summary_municipio.to_csv(DATA_OUT_DIR / "coalizione_sinistra_section_summary_municipio3_2021.csv", index=False)
    print("Done.", flush=True)


if __name__ == "__main__":
    main()
