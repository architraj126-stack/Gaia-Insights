**EARTH SCIENCE EXPLORER**

Complete Prototype Product & Technical Specification

Homepage + five analysis pages \| UX, features, data, backend and
scientific workflow

**VERSION 1.0 • 13 NOVEMBER 2026**


*A working build specification. Dataset endpoints, product versions and
observation coverage must be validated against official catalogues at
runtime.*

# Document Control

  -----------------------------------------------------------------------
  **Item**                            **Details**
  ----------------------------------- -----------------------------------
  Project name                        Earth Science Explorer

  Document                            Complete prototype product and
                                      technical specification

  Version / date                      Version 1.0 -- 13 November 2026

  Scope                               Homepage, Data Explorer, Geographic
                                      Explorer, Trend Analysis, Change
                                      Detection, Significance & Reports

  Intended audience                   Prototype designers, frontend
                                      developers, backend developers,
                                      data engineers and hackathon
                                      reviewers

  Status                              Design blueprint consolidated from
                                      the project discussion;
                                      implementation and dataset
                                      validation remain to be completed
  -----------------------------------------------------------------------

+-----------------------------------------------------------------------+
| **Important scope note**                                              |
|                                                                       |
| This document records the agreed product direction and recommended    |
| technical implementation. It is not evidence that the application,    |
| integrations, calculations or NASA data pipelines have already been   |
| implemented. All numeric examples and sample graph values are         |
| illustrative unless explicitly identified as dataset metadata.        |
+=======================================================================+
+-----------------------------------------------------------------------+

# Contents

-   1\. Product overview and goals

-   2\. User journey and application navigation

-   3\. Global design system and shared interaction rules

-   4\. Homepage -- landing experience

-   5\. Page 1 -- Data Explorer

-   6\. Dataset catalogue and scientific data decisions

-   7\. Page 2 -- Geographic Explorer

-   8\. Page 3 -- Trend Analysis

-   9\. Page 4 -- Change Detection

-   10\. Page 5 -- Significance & Reports

-   11\. End-to-end system architecture

-   12\. Backend services and API contract

-   13\. Shared data model and state

-   14\. Scientific processing and calculation rules

-   15\. Data access, provenance and update handling

-   16\. Quality, security, performance and accessibility

-   17\. Build roadmap and acceptance criteria

-   18\. Official references and technical documentation

The page blueprints are intentionally separated from implementation
notes. UI sections define what the user sees; backend sections define
how the application should produce those results.

# 1. Product Overview and Goals

Earth Science Explorer is a web application for exploring historical
Earth-science observations, analysing environmental trends over time,
comparing spatial change between periods, testing statistical evidence
and exporting a traceable research-style report.

## 1.1 Core problem the application solves

Earth-science datasets are distributed across multiple providers, have
different spatial and temporal resolutions, and do not all cover the
same years or locations. The application brings a guided workflow into
one interface while making coverage limitations, data quality and method
assumptions visible.

## 1.2 Main questions users can answer

1.  What environmental variable do I want to study?

2.  Where on Earth do I want to study it?

3.  How has it changed over the historical record?

4.  Where are the greatest increases and decreases occurring?

5.  Are the observed trends or spatial changes statistically
    significant?

6.  Can I export the analysis with its data sources, methods and
    limitations?

## 1.3 Product goals

  -----------------------------------------------------------------------
  **Goal**                            **Product behaviour**
  ----------------------------------- -----------------------------------
  Guided analysis                     A five-stage workflow from dataset
                                      selection through reporting.

  Historical perspective              Default analysis start is 1990,
                                      with the end date driven by each
                                      product's latest complete
                                      observation.

  Global exploration                  A global map, region search and
                                      custom geometry selection.

  Scientific transparency             Show dataset version, units,
                                      coverage, resolution, missing data
                                      and analysis methods.

  Spatial understanding               Map grid-cell changes rather than
                                      presenting only one region-wide
                                      number.

  Reproducible reporting              Store enough provenance to explain
                                      how a displayed result was
                                      generated.
  -----------------------------------------------------------------------

## 1.4 What is out of scope for the first prototype

-   Machine-learning forecasting or future climate prediction.

-   Causal attribution: a statistical trend does not by itself prove why
    a change happened.

-   A fully general-purpose archive for every NASA dataset. The
    prototype starts with a curated, tested catalogue.

-   Treating every variable as available over every location and every
    date.

-   Calculating from map screenshots, colourised browse images or
    unverified sample values.

# 2. User Journey and Application Navigation

The application consists of one public landing page and five analysis
pages. The user progresses through a guided workflow. Selections made
earlier are carried forward; users should not have to re-enter the same
variable or region on every page.

  ----------------------------------------------------------------------------
  **Step**       **Page**       **Primary      **User         **Main output**
                                question**     action**       
  -------------- -------------- -------------- -------------- ----------------
  0              Homepage       What can this  Understand the Entry into Data
                                tool do?       product and    Explorer.
                                               click Start    
                                               Exploring.     

  1              Data Explorer  What should I  Choose         Selected dataset
                                study?         variable,      configuration.
                                               product, time  
                                               period and     
                                               frequency.     

  2              Geographic     Where should I Choose a       Validated
                 Explorer       study?         boundary or    study-area
                                               draw a         geometry and
                                               geometry.      availability
                                                              summary.

  3              Trend Analysis How did it     Choose         Time series,
                                change over    aggregation    trend estimate
                                time?          and graph      and data-quality
                                               options.       summary.

  4              Change         Where did it   Choose         Difference
                 Detection      change?        baseline and   raster and
                                               comparison     spatial summary.
                                               periods and    
                                               map mode.      

  5              Significance & How strong is  Review         Validated
                 Reports        the evidence?  statistical    interpretation
                                               results and    and downloadable
                                               select report  outputs.
                                               sections.      
  ----------------------------------------------------------------------------

+-----------------------------------------------------------------------+
| **Navigation rule**                                                   |
|                                                                       |
| Keep a persistent page navigation or step indicator on the analysis   |
| pages. The user can revisit previous pages, but changing a dataset,   |
| date range or geometry must invalidate and recalculate downstream     |
| results that depend on it.                                            |
+=======================================================================+
+-----------------------------------------------------------------------+

# 3. Global Design System and Shared Interaction Rules

## 3.1 Visual direction

  -----------------------------------------------------------------------
  **Design element**                  **Recommendation**
  ----------------------------------- -----------------------------------
  Theme                               Dark navy / deep charcoal interface
                                      with clear blue and cyan accents.

  Typography                          Modern sans-serif; strong
                                      hierarchy, readable body size and
                                      compact labels.

  Cards                               Rounded corners, subtle borders and
                                      restrained shadows.

  Maps                                Large map canvas, visible legend,
                                      clear no-data treatment and simple
                                      layer controls.

  Charts                              High contrast axes, clear units,
                                      tooltips, accessible line styles
                                      and export actions.

  Spacing                             Use generous whitespace. Keep
                                      settings compact and data
                                      visualisations dominant.

  Responsive behaviour                Three-column desktop dashboards
                                      collapse into stacked or
                                      drawer-based layouts on tablets and
                                      phones.
  -----------------------------------------------------------------------

## 3.2 Reusable UI elements

-   Top navigation / logo / breadcrumb / step indicator.

-   Dataset card with source, unit, resolution, temporal coverage and
    availability status.

-   Region summary chip and selected-variable chip.

-   Date-range controls constrained by data availability.

-   Map legend and layer selector.

-   Chart toolbar: aggregation, trend line, moving average, confidence
    band and export.

-   Status chips: Available, Partial, Unavailable, Loading, Failed and
    Needs validation.

-   Expandable methodology, metadata and data-quality sections.

-   Report preview and export controls.

## 3.3 Global application states

  -----------------------------------------------------------------------
  **State**                           **Expected UI response**
  ----------------------------------- -----------------------------------
  Loading                             Show a progress message and keep
                                      the user's selections visible.

  Available                           Allow the action and show the
                                      actual date coverage.

  Partial coverage                    Explain which dates, cells or parts
                                      of the region are missing.

  Unavailable                         Disable analysis for the affected
                                      dataset/region/date combination and
                                      explain why.

  No valid data                       Show an honest empty state; do not
                                      draw zeros or fabricate graph
                                      points.

  Stale result                        Tell the user which input changed
                                      and offer recalculation.

  Error                               Show a recoverable error message
                                      and request/job identifier for
                                      support.
  -----------------------------------------------------------------------

# 4. Homepage -- Landing Experience

Purpose: explain the value of the platform and guide users into Page 1.
The homepage is a landing page, not another analysis dashboard.


Figure 1. Generated homepage wireframe used as the visual reference for
the landing-page structure.

## 4.1 Navigation bar

  -----------------------------------------------------------------------
  **Element**                         **Behaviour**
  ----------------------------------- -----------------------------------
  Project logo / name                 Earth Science Explorer branding;
                                      returns to homepage.

  Home                                Returns to landing page.

  Explore                             Opens the Data Explorer.

  About                               Scrolls to or opens a project
                                      overview.

  Data Sources                        Opens source and dataset
                                      documentation.

  Get Started                         Primary CTA; opens Page 1.
  -----------------------------------------------------------------------

## 4.2 Hero section

Desktop layout: copy on the left and a large Earth-from-space visual on
the right. On smaller screens, stack the text above the image.

**Suggested headline:** "Understand Our Changing Earth."

**Suggested description:** "Explore decades of Earth-science data,
visualize environmental changes and discover how our planet is evolving
through historical observations and scientific analysis."

-   Primary button: Start Exploring → Page 1.

-   Secondary button: Learn More → scrolls to How It Works.

-   Visual: Earth-from-space image with dark overlay/gradient so text
    remains readable.

## 4.3 What You Can Do cards

  -----------------------------------------------------------------------
  **Card**                **Description**         **Destination**
  ----------------------- ----------------------- -----------------------
  Explore Data            Access historical       Page 1
                          environmental datasets  
                          from NASA and           
                          authoritative sources.  

  Analyse Trends          Understand how          Page 3 overview or Page
                          environmental variables 1 start
                          change over time.       

  Detect Changes          Find geographical areas Page 4 overview or Page
                          experiencing            1 start
                          environmental changes.  

  Generate Reports        Validate findings and   Page 5 preview or Page
                          export research-ready   1 start
                          reports.                
  -----------------------------------------------------------------------

## 4.4 How It Works section

A five-step horizontal workflow: (1) Explore Data, (2) Select Geography,
(3) Analyse Trends, (4) Detect Changes, (5) Validate & Report. Each step
uses a numbered marker, short title and one-line explanation. On mobile,
convert it to a vertical timeline.

## 4.5 Explore Earth-science variables

Show a small set of visual cards: Precipitation, Land Surface
Temperature, Soil Moisture, and Ocean & Atmospheric Variables. Each card
links to Page 1 with the relevant variable preselected. Only show
variables that are actually configured in the application catalogue.

## 4.6 Final CTA and footer

Final CTA: "Discover the Story Behind Earth's Data." Button: "Begin Your
Analysis". Footer includes project name, About, Data Sources,
Methodology, contact/help information, dataset attribution and a note
that analysis is subject to dataset coverage and limitations.

+-----------------------------------------------------------------------+
| **Homepage must not show**                                            |
|                                                                       |
| Do not place a large interactive map, trend graphs, statistical       |
| results or dataset configuration forms on the homepage. These belong  |
| to Pages 1--5.                                                        |
+=======================================================================+
+-----------------------------------------------------------------------+

# 5. Page 1 -- Data Explorer

Purpose: let the user choose what to study. It is a data-selection and
configuration page. It should not be dominated by a global map; the map
belongs on Page 2.

## 5.1 Layout

  -----------------------------------------------------------------------
  **Area**                            **Contents**
  ----------------------------------- -----------------------------------
  Header                              Page title "Data Explorer", short
                                      explanation and step indicator.

  Search / filters                    Search variable or dataset;
                                      category filters such as All, Land,
                                      Ocean and Atmosphere.

  Main variable catalogue             Variable cards with image, label,
                                      source, units, description,
                                      scientific question, coverage and
                                      preview.

  Details drawer                      Expanded metadata, version,
                                      temporal/spatial resolution,
                                      geography, missing-data notes and
                                      source link.

  Configuration area                  Start year, end date, time
                                      frequency and dataset/product
                                      selection.

  Selection summary                   Selected variable(s), dataset(s),
                                      units, dates and availability.

  Primary CTA                         Continue to Geographic Explorer.
  -----------------------------------------------------------------------

## 5.2 Variable card content

-   Variable name and category.

-   Dataset / product name and provider.

-   Native unit and any displayed unit conversion.

-   One-sentence explanation.

-   "What can we discover?" prompt to explain possible analysis.

-   Historical start date and latest known observation date (dynamically
    retrieved).

-   Spatial and temporal resolution.

-   Small preview graph only when actual numerical data are loaded.

## 5.3 Configuration defaults

  -----------------------------------------------------------------------
  **Control**                         **Default / rule**
  ----------------------------------- -----------------------------------
  Start date                          1990-01-01 for the project's
                                      historical analysis, unless product
                                      availability starts later.

  End date                            Latest complete observation date
                                      for the selected dataset; never set
                                      to current calendar date
                                      automatically.

  Frequency                           Monthly by default where the
                                      selected product supports it.

  Dataset version                     Must be explicit and pinned in the
                                      analysis provenance.

  Multiple variables                  Allow more than one variable to be
                                      selected, but use one variable at a
                                      time in the Page 2 raster display
                                      to avoid map clutter.
  -----------------------------------------------------------------------

## 5.4 Preview graph rule

A historical preview is shown only if the application has real values
available. Early mockup graphs are placeholders and must never be
presented as measured data. Label sample/mock data as illustrative if
used during design demos.

## 5.5 Page 1 output state

On Continue, persist dataset IDs, variable IDs, selected versions,
units, start/end dates, aggregation/frequency, spatial coverage metadata
and source citation. Page 2 reads these values; it does not ask the user
to pick the variables again.

# 6. Dataset Catalogue and Scientific Data Decisions

The application is designed around an analysis start of 1990. The
selected products must support that date, but not every product has
identical coverage, resolution or update latency. The app must display
the true coverage per dataset.

## 6.1 Initial curated variables

  -----------------------------------------------------------------------------
  **App variable**  **Proposed product **Coverage &      **Important caveat /
                    / field**          resolution**      implementation
                                                         decision**
  ----------------- ------------------ ----------------- ----------------------
  Precipitation     GPCP monthly       Global; monthly.  Do not mix versions
                    satellite--gauge   V2.3: 2.5° ×      invisibly. V3.3 has
                    analysis. Prefer a 2.5°. V3.3: 0.5°  documented
                    pinned product     × 0.5°.           early-period ocean
                    version. GPCP V2.3                   sampling/consistency
                    is the legacy 2.5°                   caveats in 1983--1991;
                    global monthly                       because the app begins
                    record from Jan                      in 1990, provide a
                    1979; GPCP V3.3 is                   sensitivity warning
                    the newer 0.5°                       for 1990--1991 ocean
                    monthly family                       trend analysis. Decide
                    beginning Jan                        the primary version
                    1983.                                during dataset
                                                         onboarding and pin it.

  Land surface      NASA MERRA-2       Global reanalysis This is a
  temperature       surface skin       grid              reanalysis/model
                    temperature TS;    approximately     surface skin
                    use the            0.5° latitude ×   temperature
                    appropriate        0.625° longitude; diagnostic, not MODIS
                    monthly            MERRA-2 begins    satellite land-surface
                    instantaneous      1980.             temperature. Use
                    single-level                         accurate label and
                    collection                           explain
                    (confirm variable                    model/reanalysis
                    presence in exact                    nature.
                    collection/file                      
                    specification                        
                    before coding).                      

  Sea surface       Prefer a dedicated Global, daily,    MERRA-2 SST is used as
  temperature       SST product such   0.25°; begins 1   a prescribed boundary
                    as NOAA OISST v2.1 Sep 1981.         condition in the
                    for ocean                            reanalysis system; do
                    temperature                          not assume a
                    analysis.                            standalone standard
                                                         MERRA-2 SST analysis
                                                         field exists. A
                                                         separate OISST product
                                                         is clearer for the
                                                         app's SST variable.

  Soil moisture     NASA GLDAS Noah    Land-only model   GLDAS-2.0 runs
                    monthly soil       coverage; common  1948--2014; GLDAS-2.1
                    moisture, with     monthly products  starts 2000 and
                    explicit version   include 0.25° and continues. The forcing
                    choice: GLDAS-2.0  1.0° grids.       differs. Do not stitch
                    or GLDAS-2.1;                        them as one
                    inspect layer                        homogeneous time
                    variable names and                   series without overlap
                    units.                               checks, bias
                                                         assessment and a clear
                                                         version transition.

  Atmospheric water MERRA-2 QV         MERRA-2 global,   Specific humidity, 2-m
  vapour / specific specific humidity  approx. 0.5° ×    specific humidity and
  humidity          on selected        0.625°, starts    total-column
                    pressure levels    1980. M2IMNPASM   precipitable water are
                    (M2IMNPASM) or a   is monthly at 42  different measures.
                    clearly defined    pressure levels.  The UI must name the
                    single-level field                   exact field and
                    such as QV2M;                        pressure level; do not
                    optionally TQV for                   call all of them
                    total precipitable                   simply "water vapour".
                    water.                               
  -----------------------------------------------------------------------------

## 6.2 Dataset metadata that must be stored

-   Human-readable product name, provider and short name / collection
    ID.

-   Version / DOI / persistent identifier.

-   Native variable short name, long name, units, valid range and fill
    value.

-   Native spatial grid, CRS, cell dimensions and spatial coverage.

-   Native temporal resolution, start date, latest observation date and
    update latency.

-   Product documentation, citation text, access URL and terms/licensing
    notes.

-   Known reprocessing, version transitions, known limitations and
    no-data mask semantics.

## 6.3 Latest observation date logic

For each selected product, query the authoritative collection/granule
metadata or data manifest and determine the newest complete observation.
Do not confuse record publication date, catalogue update date, granule
creation date or reprocessing date with the date of the observation
itself. Monthly time series should default to the last complete month,
not an incomplete current month.

+-----------------------------------------------------------------------+
| **Critical coverage rule**                                            |
|                                                                       |
| A global basemap does not mean every data variable is valid           |
| everywhere. Soil moisture is land-only; SST is ocean-only; some       |
| products have latitude limits, coarse cells or missing observations.  |
| The application must maintain a per-dataset coverage mask and show    |
| partial/unavailable states.                                           |
+=======================================================================+
+-----------------------------------------------------------------------+

## 6.4 Version and continuity policy

A dataset version change creates a provenance event. Do not silently
append a new version to an old record. Before using a new version in a
historical trend, assess overlap, recalibration, variable definition,
units, resolution and discontinuity risk. Keep a version-aware dataset
registry and permit the user to see which version generated the result.

# 7. Page 2 -- Geographic Explorer

Purpose: let the user select where the analysis should take place and
preview whether the chosen datasets contain usable data in that region.

## 7.1 Three-column desktop layout

  -----------------------------------------------------------------------------
  **Panel**               **Approx. width**       **Purpose and controls**
  ----------------------- ----------------------- -----------------------------
  Left: Region selection  23%                     Search
                                                  country/state/district/city
                                                  where available; choose
                                                  administrative boundary, draw
                                                  polygon, draw rectangle, or
                                                  point plus buffer. Show
                                                  already-selected variables
                                                  from Page 1.

  Centre: Interactive map 52%                     Large global map with
                                                  pan/zoom; base-map switcher;
                                                  administrative outlines;
                                                  selected geometry; one active
                                                  science raster at a time;
                                                  legend; date/month control;
                                                  opacity; fullscreen/reset.

  Right: Region details   25%                     Selected region name/type,
                                                  approximate area, coordinate
                                                  bounds/centroid, dataset
                                                  availability per variable,
                                                  product metadata and
                                                  warnings.
  -----------------------------------------------------------------------------

## 7.2 Region selection modes

  -----------------------------------------------------------------------
  **Mode**                            **Expected behaviour**
  ----------------------------------- -----------------------------------
  Administrative boundary (default)   Search and select a supported
                                      boundary such as country,
                                      state/province, district or city.
                                      The chosen boundary is represented
                                      as GeoJSON geometry.

  Draw polygon                        User digitises a custom polygon.
                                      Support edit, delete, clear and
                                      undo if available in the
                                      map-drawing library.

  Draw rectangle                      User drags a rectangle to define a
                                      bounding area.

  Point + buffer                      User selects a point and a radius.
                                      Backend converts this into a
                                      polygon/buffer using a suitable
                                      projected/geodesic calculation.

  Search                              Search place names against a
                                      boundary/geocoding source. Always
                                      show the resolved feature before
                                      committing.
  -----------------------------------------------------------------------

## 7.3 Map components and controls

-   Base map selector: street / satellite / terrain where a permitted
    tile source is configured.

-   Zoom in/out, reset view, fullscreen and locate selected geometry.

-   Boundary outline and optional administrative overlay.

-   Variable/raster selector; show one variable layer at a time by
    default.

-   Scientific raster overlay with data date, dataset source, units,
    colour scale and missing-data mask.

-   Date controls constrained to the selected dataset's actual dates.

-   Opacity control for raster overlay.

-   Legend with units, min/max or classification thresholds and a
    no-data swatch.

## 7.4 Right-side availability panel

For each selected variable, show Available / Partial / Unavailable.
Include product version, observation coverage in the selected region,
spatial resolution, temporal resolution, units, provider and a short
caveat. Warn if the user's polygon is much smaller than a coarse cell or
if the selected region contains very few valid cells.

## 7.5 Map/data separation

+-----------------------------------------------------------------------+
| **Important implementation rule**                                     |
|                                                                       |
| NASA GIBS is an imagery-browse service (for supported visual layers   |
| and dates). It is not the numerical raster source for trend           |
| calculations. Obtain scientific values from the underlying NetCDF,    |
| HDF, Zarr or GeoTIFF data product. Never calculate a trend by         |
| sampling screen colours from GIBS tiles.                              |
+=======================================================================+
+-----------------------------------------------------------------------+

## 7.6 Page 2 output

Persist the selected region geometry (GeoJSON, CRS and geometry
metadata), region label/type, area, selected variables, per-variable
availability response and active map date. Page 3 needs the actual
geometry, not merely a region name.

# 8. Page 3 -- Trend Analysis

Purpose: show how the selected variable changed over time within the
selected geometry. This is the main time-series and regional trend page.

## 8.1 Layout

  -------------------------------------------------------------------------
  **Panel**               **Approx. width**       **Contents**
  ----------------------- ----------------------- -------------------------
  Left: Analysis settings 23%                     Selected variable(s),
                                                  selected region summary,
                                                  valid date range,
                                                  monthly/annual/seasonal
                                                  aggregation and graph
                                                  toggles.

  Centre: Historical      52%                     Interactive Plotly
  graph                                           time-series chart,
                                                  observed values, trend
                                                  line, optional moving
                                                  average and confidence
                                                  band, tooltips, zoom,
                                                  export and optional
                                                  annual overview.

  Right: Trend summary    25%                     Direction, annual rate of
                                                  change, average value,
                                                  estimated total change,
                                                  valid observation count
                                                  and completeness.
  -------------------------------------------------------------------------

## 8.2 Inputs inherited from earlier pages

-   Variable and dataset/version from Page 1.

-   Selected region geometry and region details from Page 2.

-   Start date default 1990 and selected end date/latest complete
    observation date.

-   Frequency and units from the product catalogue.

## 8.3 Left settings

  -----------------------------------------------------------------------
  **Control**                         **Behaviour**
  ----------------------------------- -----------------------------------
  Variable selector                   Select among variables already
                                      chosen on Page 1; switching
                                      variable refreshes the series and
                                      metadata.

  Region                              Read-only region label with a link
                                      to revise the region on Page 2.

  Date range                          Respect product availability and
                                      selected-region valid coverage.

  Aggregation                         Monthly (default), Annual,
                                      Seasonal.

  Trend line                          Toggle regression fit or selected
                                      robust slope display.

  Moving average                      Optional smoothing; display window
                                      length and clarify it is a visual
                                      aid.

  Confidence interval                 Optional band around estimate where
                                      method supports it.

  Data points                         Toggle individual monthly
                                      observations / points.
  -----------------------------------------------------------------------

## 8.4 Centre graph

-   X-axis: date/time. Y-axis: variable measurement and units.

-   Observed time-series line/points, with data gaps preserved rather
    than interpolated silently.

-   Trend line should be visually distinct from observed values.

-   Tooltips show timestamp, value, units and any data quality flag.

-   Zoom/pan and reset controls.

-   Export chart as image; CSV export for plotted values.

-   Optional annual/seasonal overview or aggregation switch.

## 8.5 Right summary metrics

  -----------------------------------------------------------------------
  **Metric**                          **Definition / display rule**
  ----------------------------------- -----------------------------------
  Trend direction                     Increasing, decreasing, no clear
                                      trend or insufficient data. Avoid
                                      claiming a trend if sample
                                      length/quality is inadequate.

  Rate of change                      Slope with units per year (e.g.
                                      °C/year, mm/year). State whether it
                                      is regression slope or Sen's slope.

  Average value                       Mean over the valid selected
                                      period, with clear aggregation
                                      meaning.

  Estimated total change              Slope multiplied by elapsed time,
                                      clearly distinguished from the
                                      annual slope.

  Data completeness                   Valid observations divided by
                                      expected observations; disclose the
                                      denominator and missing-data
                                      handling.

  Valid sample size                   Count of time steps included after
                                      filters and quality checks.
  -----------------------------------------------------------------------

## 8.6 Scientific aggregation rules

Do not apply the same aggregation rule to every variable. Rainfall
represented as a monthly rate (for example mm/day) must be converted to
monthly accumulation using the number of days in each month before
annual totals are formed. Temperature is generally averaged across valid
monthly values. Soil moisture is generally averaged over the target
period. The exact conversion must respect the native product units and
whether values are rates, accumulations or states.

## 8.7 Trend methods

  --------------------------------------------------------------------------------
  **Method**              **Role in Page 3**      **Caution**
  ----------------------- ----------------------- --------------------------------
  Linear regression       Estimate a linear rate  Seasonality, outliers and
                          of change and fitted    autocorrelation can affect
                          trend line.             inference.

  Mann--Kendall           Test for a monotonic    Standard version assumes
                          trend.                  independence; consider
                                                  seasonal/autocorrelation-aware
                                                  variants.

  Seasonal Mann--Kendall  Test monotonic trends   Appropriate seasonal grouping
                          while grouping          must be defined.
                          observations by         
                          season/month.           

  Sen's slope             Robust estimate of      Report units and confidence
                          monotonic trend         interval; not the same as
                          magnitude.              regression slope.
  --------------------------------------------------------------------------------

## 8.8 Bottom data table

Expandable table lists the dates and processed values used in the graph.
Include download CSV, pagination/virtual scrolling for long monthly
series, valid/missing flags and units. The table must correspond to the
plotted data and selected aggregation.

## 8.9 What Page 3 does not do

No new region discovery, no main world-map selection, no spatial
comparison maps, no detailed multi-test significance report and no full
PDF report. Those belong to Pages 2, 4 and 5.

# 9. Page 4 -- Change Detection

Purpose: show where an environmental variable increased or decreased
between two historical periods. Page 4 is spatially focused, with a
large map and a spatial summary.

## 9.1 Layout

  ------------------------------------------------------------------------
  **Panel**               **Approx. width**       **Contents**
  ----------------------- ----------------------- ------------------------
  Left: Change settings   23%                     Variable, region,
                                                  baseline period,
                                                  comparison period,
                                                  change metric and map
                                                  display mode.

  Centre: Change map      52%                     Interactive difference
                                                  raster map, diverging
                                                  colour scale, legend,
                                                  region outline, opacity,
                                                  click-to-inspect grid
                                                  cell and optional
                                                  side-by-side/swipe
                                                  comparison.

  Right: Spatial summary  25%                     Overall area-weighted
                                                  change, area share
                                                  increasing/decreasing,
                                                  highest/lowest valid
                                                  change and no-data area.
  ------------------------------------------------------------------------

## 9.2 Comparison period defaults

+-----------------------------------------------------------------------+
| **Default periods are examples, not a data cutoff**                   |
|                                                                       |
| Initial comparison example: Baseline 1990--2005; Comparison           |
| 2006--latest complete available period. The application must retain   |
| all valid data after 2005. Users can edit both periods, and every     |
| selection must stay within actual product coverage.                   |
+=======================================================================+
+-----------------------------------------------------------------------+

## 9.3 Settings and methods

  -----------------------------------------------------------------------
  **Control**                         **Options / rule**
  ----------------------------------- -----------------------------------
  Variable                            Inherited from Page 1; allow
                                      switching among configured
                                      variables.

  Region                              Inherited from Page 2; revise there
                                      if needed.

  Baseline period                     User-configurable start/end years
                                      within data availability.

  Comparison period                   User-configurable start/end years;
                                      default ends at latest complete
                                      common period.

  Absolute change                     Difference in native units:
                                      comparison mean minus baseline
                                      mean.

  Percentage change                   Relative difference; show only
                                      where mathematically meaningful and
                                      baseline is not near zero.

  Spatial trend                       Per-cell slope over time, with
                                      units per year; distinct from
                                      two-period difference.

  Temporal aggregation                Annual or seasonal grouping as
                                      appropriate to the variable.
  -----------------------------------------------------------------------

## 9.4 Core calculation

For every valid grid cell i, calculate the baseline statistic Aᵢ and
comparison statistic Bᵢ using the same variable, compatible
product/version, spatial grid, units and matching seasonal/aggregation
rule. The difference is Δᵢ = Bᵢ − Aᵢ. Preserve missing cells as No Data;
do not substitute zero.

## 9.5 Map design

-   Diverging scale centred at zero: red for positive change, blue for
    negative change, neutral for small/no change and grey/transparent
    for missing data.

-   Legend includes units, range and threshold definitions.

-   Click/hover a valid cell to show location, value, baseline mean,
    comparison mean and difference.

-   Map controls: zoom, fullscreen, opacity, layer/metric selector,
    reset and region boundary.

-   Support side-by-side maps or swipe comparison as a later
    enhancement; the first implementation should prioritise a difference
    map.

-   Map export as PNG and, where useful, export the difference raster as
    GeoTIFF/COG.

## 9.6 Spatial summary

  -----------------------------------------------------------------------
  **Metric**                          **Calculation/display**
  ----------------------------------- -----------------------------------
  Overall change                      Area-weighted regional summary of
                                      valid grid-cell differences.

  Area increasing                     Sum of valid grid-cell area with
                                      positive change divided by total
                                      valid area.

  Area decreasing                     Sum of valid grid-cell area with
                                      negative change divided by total
                                      valid area.

  Highest change                      Maximum positive change, with
                                      location/region label.

  Lowest change                       Most negative change, with
                                      location/region label.

  No-data area                        Area lacking valid values, shown
                                      separately from stable/no-change
                                      area.
  -----------------------------------------------------------------------

## 9.7 Important spatial handling

-   Use cell-area weighting on latitude/longitude grids; pixel counts
    are not equal-area globally.

-   Apply selected polygon fractions where practical so boundary cells
    are not treated as fully inside when only partly intersecting.

-   Warn when a study area is much smaller than the grid cell size or
    contains too few valid grid cells.

-   Check land/ocean coverage. Soil moisture should not produce ocean
    values; SST should not produce land values.

-   Percentage change can be misleading when baseline values are zero,
    near zero, negative or signed. Offer absolute difference instead.

## 9.8 Significance handoff

Page 4 displays estimated spatial differences. It must not label a
change "statistically significant" merely because the magnitude is
large. Page 5 tests the historical samples at each grid cell or region
and then classifies the evidence.

# 10. Page 5 -- Significance & Reports

Purpose: assess whether observed trends or spatial changes have
statistical support, explain uncertainty and create a traceable report
combining outputs from Pages 1--4.

## 10.1 Layout

  -----------------------------------------------------------------------
  **Panel / section**                 **Contents**
  ----------------------------------- -----------------------------------
  Left: Analysis settings             Regional trend or spatial test,
                                      recommended method, confidence
                                      level (default 95%), significance
                                      threshold α (default 0.05),
                                      autocorrelation and
                                      multiple-testing options.

  Centre: Significance visualization  Switch between regional trend
                                      results and spatial significance
                                      map.

  Right: Statistical results          P-value, confidence interval, test
                                      statistic, slope estimate, sample
                                      size and interpretation.

  Bottom: Data quality & methodology  Coverage, missing observations,
                                      dataset version, resolution,
                                      autocorrelation and method
                                      limitations.

  Bottom: Report generator            Choose report sections, preview
                                      report, export PDF, CSV and PNG/map
                                      assets.
  -----------------------------------------------------------------------

## 10.2 Inputs

Reuse Page 3 time series and Page 4 spatial fields/results, but preserve
access to the underlying historical time series per grid cell. A
difference raster alone is not sufficient to determine statistical
significance.

## 10.3 Regional trend significance

For a selected region, test the regional time series derived with
valid-cell and area-weighting rules. Show the test name, null
hypothesis, statistic, p-value, estimated slope, confidence interval and
data sample count. Include an understandable interpretation, not just a
green badge.

## 10.4 Spatial significance

For each valid grid cell, test the underlying sequence of historical
observations or a suitable statistical model. Apply a multiple-testing
correction such as Benjamini--Hochberg False Discovery Rate (FDR)
because thousands of per-cell tests increase false-positive risk. Show
whether map significance reflects raw or adjusted p-values.

  -----------------------------------------------------------------------
  **Map class**                       **Interpretation**
  ----------------------------------- -----------------------------------
  Significant increase                Positive estimated change with
                                      adjusted statistical evidence
                                      meeting the configured threshold.

  Significant decrease                Negative estimated change with
                                      adjusted statistical evidence
                                      meeting the configured threshold.

  Not significant                     A valid estimate exists but does
                                      not meet the evidence threshold.

  Insufficient data                   Not enough valid observations to
                                      run the selected test reliably.

  Not covered                         The dataset has no valid coverage
                                      for that location.
  -----------------------------------------------------------------------

## 10.5 Statistical metrics

  -----------------------------------------------------------------------
  **Metric**                          **Meaning and user-facing
                                      explanation**
  ----------------------------------- -----------------------------------
  P-value                             Evidence against the null
                                      hypothesis under the test
                                      assumptions. It is not the
                                      probability that the null
                                      hypothesis is true.

  Confidence interval                 Interval of plausible values for an
                                      estimate under the chosen
                                      method/assumptions.

  Test statistic                      The numerical statistic produced by
                                      the test; label the specific test
                                      and units if applicable.

  Trend estimate                      Slope in measurement units per
                                      year; distinguish Sen's slope from
                                      regression slope.

  Sample size                         Number of valid temporal
                                      observations used.

  Significance threshold              Default α = 0.05; expose as a
                                      configurable expert option.

  Adjusted p-value                    Use for spatial multiple-test
                                      correction; display correction
                                      method.
  -----------------------------------------------------------------------

## 10.6 Statistical cautions

-   Monthly climate series are seasonal; use seasonal grouping or
    appropriate models when needed.

-   Autocorrelation can inflate significance if ignored. Consider a
    suitable correction, pre-whitening or block-bootstrap approach and
    document the choice.

-   Statistical significance does not imply large environmental impact
    or causal explanation. Show both effect size and evidence strength.

-   Confidence intervals must be generated by the method used; do not
    show an arbitrary ± value.

-   For regional means, handle area weights and missing observations
    consistently.

-   A grid-cell map requires FDR or another predeclared multiple-testing
    strategy.

## 10.7 Report generator

User-selectable sections, all selected by default:

-   Executive summary -- short plain-language findings.

-   Dataset and study area -- variables, provider, collection/version,
    DOI, region, dates, resolution and units.

-   Historical trend analysis -- Page 3 chart, aggregation, slope,
    averages and completeness.

-   Spatial change detection -- Page 4 difference map, period
    definitions and spatial summaries.

-   Statistical significance -- tests, assumptions, raw/adjusted
    p-values, confidence intervals and interpretation.

-   Data quality and limitations -- missing data, coverage,
    scale/resolution, version transitions and caveats.

-   Methodology and references -- equations, algorithm/method
    description, product citations and access dates.

## 10.8 Export formats

  -----------------------------------------------------------------------
  **Format**                          **Contents**
  ----------------------------------- -----------------------------------
  PDF                                 Full report with title, executive
                                      summary, metadata, graphs, maps,
                                      statistical results, methods,
                                      limitations and source citations.

  CSV                                 Processed time-series values, cell
                                      summaries or region comparison
                                      table; include units and quality
                                      flags.

  PNG                                 Chart and map images for use in
                                      presentations or publications.

  GeoTIFF / COG (recommended          Spatial difference or significance
  extension)                          raster for use in GIS, subject to
                                      implementation effort.
  -----------------------------------------------------------------------

# 11. End-to-End System Architecture

## 11.1 Recommended technology stack

  -----------------------------------------------------------------------
  **Layer**               **Recommended           **Responsibilities**
                          technology**            
  ----------------------- ----------------------- -----------------------
  Frontend                React + TypeScript +    Application shell,
                          Tailwind CSS            route navigation, page
                                                  layouts, shared state,
                                                  forms and responsive
                                                  UI.

  Charts                  Plotly.js               Historical time series,
                                                  confidence bands,
                                                  interactive tooltips,
                                                  chart export.

  Mapping                 React Leaflet / Leaflet Basemap, geometry
                                                  editing, raster
                                                  overlay, legend and map
                                                  interactions.

  Geometry editing        Leaflet-Geoman (or      Draw/edit polygon,
                          supported equivalent)   rectangle and
                                                  point-buffer shapes.

  Backend API             Python + FastAPI        Dataset catalogue,
                                                  input validation,
                                                  analysis jobs, result
                                                  endpoints and report
                                                  generation.

  Scientific arrays       Xarray + NumPy + Pandas Open multi-dimensional
                                                  data, select
                                                  time/space, calculate
                                                  aggregates and series.

  Geospatial              GeoPandas + Shapely +   Geometry validation,
                          Rasterio / rioxarray +  clipping/masking,
                          PyProj                  raster IO, CRS
                                                  operations and area
                                                  calculations.

  Statistics              SciPy + PyMannKendall + Regression,
                          Statsmodels             non-parametric trend
                                                  tests, confidence
                                                  intervals and FDR
                                                  correction.

  Storage                 PostgreSQL + PostGIS;   Store region
                          object storage for      geometries, run
                          NetCDF/Zarr/COG         metadata, catalogue
                                                  metadata, generated
                                                  outputs and cached
                                                  data.

  Optional performance    Dask / task queue /     Parallel array
                          Redis                   processing and
                                                  long-running jobs; add
                                                  only when workload
                                                  requires it.
  -----------------------------------------------------------------------

## 11.2 Logical architecture

  -----------------------------------------------------------------------
  USER BROWSER\
  React + TypeScript + Tailwind\
  ├── Homepage\
  ├── Page 1: Data Explorer\
  ├── Page 2: Geographic Explorer (Leaflet)\
  ├── Page 3: Trend Analysis (Plotly)\
  ├── Page 4: Change Detection (Leaflet raster)\
  └── Page 5: Significance & Reports\
  │ HTTPS / JSON\
  ▼\
  FASTAPI BACKEND\
  ├── Catalogue service\
  ├── Availability / coverage service\
  ├── Region / geometry service\
  ├── Data access / subsetting service\
  ├── Time-series analysis service\
  ├── Spatial change service\
  ├── Statistical significance service\
  └── Report / export service\
  │\
  ├── NASA CMR / GES DISC / Harmony / Earthdata\
  ├── NOAA / authoritative product providers\
  ├── NetCDF / HDF / Zarr / GeoTIFF\
  └── PostgreSQL + PostGIS + file/object storage
  -----------------------------------------------------------------------

  -----------------------------------------------------------------------

## 11.3 Data flow, page by page

-   Page 1 saves a selected variable, dataset ID/version, units,
    frequency and date range.

-   Page 2 resolves and validates a region; saves geometry as GeoJSON
    with CRS and computes coverage per selected dataset.

-   Page 3 backend reads/subsets actual numerical data, masks the
    geometry, creates a regional time series and calculates trend
    summaries.

-   Page 4 backend calculates baseline/comparison summaries and produces
    a georeferenced difference raster plus spatial statistics.

-   Page 5 runs inferential tests using the underlying temporal samples,
    generates significance layers and combines all outputs into a
    reproducible report.

# 12. Backend Services and API Contract

The endpoints below are a recommended interface contract for the
prototype. Exact response shapes can be refined during implementation,
but keep each endpoint focused and return traceable IDs, dataset
metadata and status information.

## 12.1 Suggested REST endpoints

  ----------------------------------------------------------------------------------------------
  **Method & endpoint**                 **Purpose**             **Typical input / output**
  ------------------------------------- ----------------------- --------------------------------
  GET /api/catalog/variables            Return configured       List of variables, display
                                        variables and their     metadata and available product
                                        dataset choices.        IDs.

  GET                                   Return products for a   Dataset name, version, units,
  /api/catalog/datasets?variable={id}   variable.               resolution, date range,
                                                                citation, source URL.

  GET /api/datasets/{id}/availability   Check temporal/spatial  Query: geometry or bbox,
                                        availability.           start/end. Response:
                                                                Available/Partial/Unavailable,
                                                                valid dates, valid cells and
                                                                warnings.

  POST /api/regions/validate            Validate and normalise  Input geometry and CRS.
                                        GeoJSON geometry.       Response: valid geometry, area,
                                                                bbox, centroid and warnings.

  POST /api/analysis/timeseries         Create Page 3           Dataset/version, variable,
                                        time-series analysis.   region geometry, dates,
                                                                aggregation and options; returns
                                                                job/result ID.

  GET /api/analysis/jobs/{job_id}       Poll long-running       Status, percent complete,
                                        analysis.               messages and result URL when
                                                                ready.

  POST /api/analysis/change-map         Create Page 4           Dataset/version, geometry,
                                        difference raster.      baseline, comparison,
                                                                aggregation and change metric.

  POST /api/analysis/significance       Create Page 5           Time-series/grid samples, test,
                                        significance results.   alpha, CI level, autocorrelation
                                                                and FDR options.

  POST /api/reports                     Generate selected       Analysis IDs, report options and
                                        report sections.        export format; returns report
                                                                job ID.

  GET /api/reports/{report_id}          Get report status and   Status, output files and
                                        download link.          provenance summary.
  ----------------------------------------------------------------------------------------------

## 12.2 Example time-series request

  -----------------------------------------------------------------------
  POST /api/analysis/timeseries\
  {\
  \"dataset_id\": \"gpcp_monthly_v23\",\
  \"dataset_version\": \"pinned-version\",\
  \"variable\": \"precipitation\",\
  \"geometry\": { \"type\": \"Polygon\", \"coordinates\": \[\] },\
  \"geometry_crs\": \"EPSG:4326\",\
  \"start_date\": \"1990-01-01\",\
  \"end_date\": \"latest_complete\",\
  \"aggregation\": \"monthly\",\
  \"options\": {\
  \"area_weighted\": true,\
  \"include_missing_flags\": true,\
  \"trend_methods\": \[\"linear_regression\", \"mann_kendall\",
  \"sen_slope\"\]\
  }\
  }
  -----------------------------------------------------------------------

  -----------------------------------------------------------------------

## 12.3 Example response shape

  -----------------------------------------------------------------------
  {\
  \"job_id\": \"job_12345\",\
  \"status\": \"completed\",\
  \"dataset\": {\
  \"id\": \"gpcp_monthly_v23\",\
  \"version\": \"pinned-version\",\
  \"units\": \"mm/day\",\
  \"source\": \"official-provider-url\"\
  },\
  \"coverage\": {\
  \"requested_start\": \"1990-01-01\",\
  \"actual_start\": \"1990-01-01\",\
  \"actual_end\": \"latest-observation-date-from-provider\",\
  \"valid_steps\": 0,\
  \"expected_steps\": 0,\
  \"completeness_pct\": null\
  },\
  \"series_url\": \"/api/results/series/series_123\",\
  \"summary\": {\
  \"trend_direction\": \"not_computed_or_result\",\
  \"slope_per_year\": null,\
  \"p_value\": null\
  },\
  \"warnings\": \[\]\
  }
  -----------------------------------------------------------------------

  -----------------------------------------------------------------------

The response is illustrative. Never return placeholder numbers or fake
IDs in a real system; all values must be populated from the actual run.

## 12.4 Long-running jobs

Spatial subsetting, raster generation, significance maps and report
rendering can be long-running. Return a job ID, expose status/progress
and allow the frontend to poll. For a small demo, synchronous processing
may be acceptable for small selections, but keep an asynchronous job
pattern available for larger regions and long periods.

# 13. Shared Data Model and State

## 13.1 Shared client state

Use one shared application state/store (for example Zustand, Redux
Toolkit or React Context for a small prototype). The exact library is
less important than keeping one source of truth across the five pages.

  -----------------------------------------------------------------------
  type AnalysisSession = {\
  sessionId: string;\
  selectedVariables: Array\<{\
  variableId: string;\
  datasetId: string;\
  datasetVersion: string;\
  fieldName: string;\
  units: string;\
  }\>;\
  dateRange: {\
  start: string; // default 1990-01-01\
  endMode: \"latest_complete\" \| \"custom\";\
  end?: string;\
  };\
  frequency: \"monthly\" \| \"annual\" \| \"seasonal\";\
  region: {\
  label: string;\
  type: \"admin\" \| \"polygon\" \| \"rectangle\" \| \"point_buffer\";\
  geometry: GeoJSON.Geometry \| null;\
  crs: string;\
  areaKm2?: number;\
  } \| null;\
  page3ResultId?: string;\
  page4ResultId?: string;\
  page5ResultId?: string;\
  };
  -----------------------------------------------------------------------

  -----------------------------------------------------------------------

## 13.2 Backend entities / tables

  -----------------------------------------------------------------------
  **Entity**                          **Key fields**
  ----------------------------------- -----------------------------------
  Variable                            id, label, category, description,
                                      unit label, default display
                                      settings.

  DatasetProduct                      id, variable_id, provider,
                                      short_name, version, DOI,
                                      temporal/spatial resolution,
                                      coverage, native units, access URL,
                                      citation.

  DatasetField                        dataset_id, field short name, long
                                      name, units, vertical level, fill
                                      value, aggregation semantics.

  Region                              id, user/session ID, name,
                                      geometry, CRS, geometry type, area,
                                      bbox.

  AnalysisRun                         id, session_id, type, request
                                      parameters, dataset/version,
                                      status, created_at, completed_at,
                                      warnings.

  AnalysisOutput                      run_id, series/raster/table paths,
                                      summary JSON, provenance, output
                                      units.

  Report                              id, selected analysis IDs, chosen
                                      sections, format, output path,
                                      citation snapshot.
  -----------------------------------------------------------------------

## 13.3 Invalidation rules

-   Changing dataset/version invalidates Page 3, Page 4 and Page 5
    outputs.

-   Changing date range invalidates any trend, difference or
    significance result that used the old dates.

-   Changing region geometry invalidates all spatial extraction and
    downstream results.

-   Changing aggregation invalidates graph, trends and period comparison
    outputs.

-   Changing test/alpha/FDR options invalidates Page 5 results but does
    not need to repeat data discovery unless the required underlying
    data is not cached.

# 14. Scientific Processing and Calculation Rules

## 14.1 Data ingestion and normalisation

-   Resolve the selected product/version using its official collection
    identifier.

-   Fetch metadata and granules for the required time/space; do not
    assume the record is continuous.

-   Read numerical fields from NetCDF/HDF/Zarr/GeoTIFF using
    Xarray/Rasterio or suitable libraries.

-   Decode coordinate reference system, time coordinate, calendar,
    units, scale/offset, fill values and quality flags.

-   Convert longitudes and coordinate ordering to a consistent internal
    convention without losing dateline geometry behaviour.

-   Validate expected time steps and build an explicit missing-time
    index.

-   Cache source files or region subsets with a key containing
    collection, version, time, geometry hash and processing settings.

## 14.2 Spatial extraction and regional mean

Mask data against the selected polygon or boundary and calculate an
area-weighted regional series. For regular latitude/longitude grids,
cell area changes with latitude; cosine(latitude) is a common
approximation for equally spaced lat/lon grids, while
geodesic/equal-area cell areas are preferable for high-stakes summaries.
For boundary cells, use fractional polygon overlap where practical.
Record the number and area of valid cells per time step.

## 14.3 Temporal aggregation

  -----------------------------------------------------------------------
  **Variable type**       **Example operation**   **Rule**
  ----------------------- ----------------------- -----------------------
  Precipitation rate      Monthly mm/day →        Multiply rate by actual
                          monthly accumulation    days in month where the
                                                  product semantics
                                                  require it; annual
                                                  rainfall is generally
                                                  the sum of monthly
                                                  accumulations.

  Temperature             Monthly mean → annual   Average valid monthly
                          mean                    means using an
                                                  appropriate time
                                                  weighting if monthly
                                                  lengths matter;
                                                  preserve unit
                                                  conversions.

  Soil moisture state     Monthly state →         Usually average valid
                          annual/seasonal mean    state measurements; do
                                                  not sum a state
                                                  variable.

  Specific humidity       QV by pressure level /  Keep the selected
                          QV2M / TQV              physical meaning and
                                                  vertical level
                                                  explicit; do not mix
                                                  pressure levels or
                                                  confuse specific
                                                  humidity with total
                                                  column water vapour.

  SST                     Daily OISST →           Use valid ocean cells
                          monthly/seasonal mean   and preserve ocean
                                                  coverage mask.
  -----------------------------------------------------------------------

## 14.4 Temperature conversion

MERRA-2 temperature fields are commonly stored in Kelvin. If displaying
degrees Celsius, convert K to °C using °C = K − 273.15 and preserve
native units in the data provenance.

## 14.5 Change detection calculations

For each grid cell i, calculate baseline value Aᵢ and comparison value
Bᵢ using consistent periods, aggregation and data rules. Absolute
difference is Δᵢ = Bᵢ − Aᵢ. Percentage change is 100 × (Bᵢ − Aᵢ) /
\|Aᵢ\| only where the baseline is meaningful and not near zero. Provide
a warning or suppress percentage mode where its interpretation is
unstable.

## 14.6 Trend testing and uncertainty

-   Fit linear regression for a linear slope and fitted line.

-   Run Mann--Kendall or Seasonal Mann--Kendall where the time series
    structure supports it.

-   Calculate Sen's slope as a robust estimate of monotonic trend
    magnitude.

-   Evaluate serial autocorrelation and select a defensible inference
    method (for example, modified MK, suitable pre-whitening or block
    bootstrap). Document the method used.

-   Calculate confidence intervals using a method appropriate to the
    estimator and dependence structure.

-   Keep p-values, test statistics, slope estimates and confidence
    intervals tied to the exact series and processing run.

## 14.7 Multiple testing for spatial maps

For a per-grid-cell significance map, apply a documented
multiple-testing correction such as Benjamini--Hochberg FDR to the set
of valid cell tests. Record both raw and adjusted p-values and the
selected threshold. Do not present a raw p-value map as if it were
already corrected.

## 14.8 No-data / low-sample handling

-   Fill values must be decoded and excluded, not converted to zero.

-   Do not interpolate across gaps unless a specific scientifically
    justified method is chosen and disclosed.

-   Set minimum valid observation thresholds before computing trends or
    comparisons.

-   Report expected vs valid samples and data completeness.

-   Distinguish "no change" from "no data" and "insufficient evidence".

# 15. Data Access, Provenance and Update Handling

## 15.1 Discovery and access services

  -----------------------------------------------------------------------
  **Service**                         **Use in the prototype**
  ----------------------------------- -----------------------------------
  NASA CMR                            Search collections/granules and
                                      inspect spatial-temporal metadata;
                                      use collection identifiers and
                                      granule metadata.

  NASA GES DISC                       Primary access/landing pages for
                                      MERRA-2 and GLDAS products; inspect
                                      product/version documentation and
                                      service alerts.

  NASA Harmony                        Use where supported to subset by
                                      time, bounding box or geometry and
                                      selected variables; verify service
                                      support for each collection.

  NASA NCCS                           Dataset descriptions and access
                                      context for supported Earth-science
                                      products.

  NASA GIBS                           Visual browse layers in maps only;
                                      use the appropriate imagery service
                                      protocol and layer/time metadata.

  NOAA NCEI / OISST                   Authoritative product source for
                                      GPCP CDR and NOAA OISST SST data
                                      where selected.
  -----------------------------------------------------------------------

## 15.2 Authentication and secret handling

-   If a provider requires Earthdata Login, authenticate from the
    backend or secure service layer, not directly in public browser
    code.

-   Store tokens/secrets in environment variables or a secret manager;
    never commit them to the repository.

-   Do not expose protected download URLs or credentials in API
    responses.

-   Respect provider access requirements, citations, terms and
    acceptable-use policies.

## 15.3 Catalogue refresh and latest-date logic

At application startup or on a controlled refresh schedule, refresh the
catalogue metadata for configured collections. At analysis request time,
query product coverage/granule availability for the requested period and
region. The interface should show "latest available observation" and
"last catalogue check" as separate timestamps.

## 15.4 Provenance saved with every output

-   Provider, collection ID, product version and DOI.

-   Native field name, units, scale/offset and conversion applied.

-   Actual observation start/end timestamps and expected/valid
    observation counts.

-   Region geometry hash, CRS, spatial mask and area-weighting approach.

-   Aggregation method, date grouping and season definition.

-   Trend method, autocorrelation handling, confidence interval method,
    alpha and FDR method.

-   Code / application version and processing timestamp.

-   Warnings and product reprocessing notices encountered.

# 16. Quality, Security, Performance and Accessibility

## 16.1 Functional testing

  -----------------------------------------------------------------------
  **Area**                            **Key tests**
  ----------------------------------- -----------------------------------
  Data catalogue                      Correct provider, product version,
                                      variables, units, dates and links.

  Availability                        Full/partial/unavailable region and
                                      date combinations; land/ocean
                                      masks.

  Geometry                            Country boundaries, custom polygon,
                                      rectangle, dateline crossing,
                                      invalid self-intersection and very
                                      small polygon.

  Time series                         Correct monthly count,
                                      missing-month flags, aggregation
                                      and unit conversions.

  Trend analysis                      Known synthetic test series with
                                      known slope; no-trend series;
                                      seasonal series; autocorrelated
                                      series.

  Change map                          Known synthetic baseline/comparison
                                      fields; sign of difference; no-data
                                      cells; boundary weighting.

  Significance                        Known effect vs null, confidence
                                      interval behaviour and FDR
                                      false-positive control.

  Report                              Metadata and figures match the
                                      exact analysis run; citations and
                                      caveats included.
  -----------------------------------------------------------------------

## 16.2 Non-functional requirements

-   Responsive design and accessible colour contrast.

-   Use clear legends, text labels and patterns so map meaning is not
    colour-only.

-   Provide keyboard-accessible controls and meaningful labels.

-   Use server-side caching for repeated data subsets and calculations.

-   Avoid downloading full global multi-decade datasets when a
    region/time subset is sufficient.

-   Use asynchronous jobs for large raster/statistical/report
    operations.

-   Log errors, job duration, provider failures and data source response
    without logging secrets.

## 16.3 Performance recommendations

-   Start with a one-variable end-to-end workflow to keep the first demo
    predictable.

-   Read only the variables, levels, times and region subset required
    for the current task.

-   Use chunked / lazy array processing for large datasets; consider
    Dask if the workload warrants it.

-   Cache processed region time series and derived rasters using strict
    versioned cache keys.

-   Prefer Cloud-Optimized GeoTIFF or tiled raster endpoints for map
    display of derived spatial results.

-   Downsample chart display for very long series only for rendering;
    keep the full series available for calculations and export.

# 17. Build Roadmap and Acceptance Criteria

## 17.1 Recommended implementation phases

  -----------------------------------------------------------------------
  **Phase**               **Build order**         **Definition of done**
  ----------------------- ----------------------- -----------------------
  0\. Foundation          React shell, routing,   Pages route correctly;
                          shared state, FastAPI   state persists; backend
                          skeleton,               health and catalogue
                          environment/config and  endpoints work.
                          dataset registry.       

  1\. Homepage + Page 1   Landing page, variable  Users can choose a real
                          cards, details drawer,  configured dataset and
                          date/product selector.  see accurate metadata.

  2\. Page 2 basic map    Global basemap,         User can select a
                          boundary                country/region and
                          search/selection,       carry geometry to Page
                          GeoJSON storage.        3.

  3\. First data pipeline Start with              A real regional
                          precipitation (GPCP)    historical series from
                          and real numerical      1990 to the latest
                          data; test coverage and complete date is
                          monthly time series.    produced with missing
                                                  values and source
                                                  metadata.

  4\. Page 3              Plotly chart,           Graph and metrics
                          aggregation controls,   reproduce from the same
                          trend estimates and     processed series.
                          CSV.                    

  5\. Page 4              Baseline/comparison     Known test rasters and
                          selectors, difference   real data produce
                          raster, map legend and  correct difference
                          area-weighted summary.  maps.

  6\. Page 5              Statistical methods,    Report exactly reflects
                          FDR for grid tests,     source metadata and
                          data-quality            outputs from the
                          explanation and report  selected analysis.
                          generation.             

  7\. Expand catalogue    Add MERRA-2             Each variable has
                          temperature, OISST,     tested units, coverage,
                          GLDAS and humidity      aggregation, land/ocean
                          fields one by one.      masks and caveats.

  8\. Hardening           Responsive UI, tests,   No placeholder results
                          error states,           are displayed as
                          performance, citations  scientific findings.
                          and final demo QA.      
  -----------------------------------------------------------------------

## 17.2 MVP priority

+-----------------------------------------------------------------------+
| **Recommended first end-to-end demo**                                 |
|                                                                       |
| Implement one variable first (precipitation), one region-selection    |
| flow, a real monthly time series, a trend result, a difference map    |
| and a minimal report. Once that complete path is reliable, add more   |
| variables. This avoids building five visually complete pages that are |
| not connected to real data.                                           |
+=======================================================================+
+-----------------------------------------------------------------------+

## 17.3 Page-level acceptance criteria

-   Homepage: Start Exploring reliably opens Page 1; no fake counts or
    unsupported coverage claims.

-   Page 1: users can select a valid product and see exact version,
    units, resolution and observation coverage.

-   Page 2: selected geometry is stored as valid GeoJSON and
    availability is computed per dataset.

-   Page 3: plotted points and displayed statistics use the same real
    processed values; missing periods remain visible.

-   Page 4: baseline/comparison periods are editable; difference sign
    and units are correct; no-data cells are not zero.

-   Page 5: significance is calculated from historical samples, spatial
    tests are corrected for multiple comparisons, and uncertainty is
    disclosed.

-   Reports: export captures the same versioned analysis outputs shown
    in the UI, including sources and limitations.

# 18. Official References and Technical Documentation

The following sources support the dataset and service decisions in this
specification. Product pages should be rechecked during implementation
because version, availability and service behaviour can change. Accessed
13 November 2026 unless a page itself reports another update date.

**\[S1\] NASA GMAO -- MERRA-2 overview --** MERRA-2 begins in 1980;
reanalysis background and description.
https://gmao.gsfc.nasa.gov/gmao-products/merra-2/

**\[S2\] NASA GMAO -- MERRA-2 system characteristics --** Approx. 0.5° ×
0.625° grid, variable output frequency and monthly latency; SST boundary
conditions are prescribed.
https://gmao.gsfc.nasa.gov/gmao-products/merra-2/system-characteristics_merra-2/

**\[S3\] NASA GES DISC -- MERRA-2 M2IMNPASM collection --** Monthly
specific humidity QV at 42 pressure levels, global coverage, product
version 5.12.4 and coverage metadata.
https://disc.gsfc.nasa.gov/datasets/M2IMNPASM_5.12.4/summary

**\[S4\] NASA GES DISC -- MERRA-2 M2IMNXASM collection record --**
Monthly single-level MERRA-2 diagnostics, including water-vapour-related
fields; confirm exact selected field.
https://catalog.data.gov/dataset/merra-2-instm_2d_asm_nx-2dmonthly-meansingle-levelassimilationsingle-level-diagnostics-0-6-224d6

**\[S5\] NOAA NCEI -- GPCP Monthly CDR V3.3 --** GPCP V3.3 monthly, 0.5°
global, begins January 1983; includes several precipitation and
uncertainty fields.
https://www.ncei.noaa.gov/access/metadata/landing-page/bin/iso?id=gov.noaa.ncdc%3AC01725

**\[S6\] NOAA PSL -- GPCP Monthly product --** GPCP V2.x-style 2.5°
global monthly record from January 1979; update and interim-data notes.
https://www.psl.noaa.gov/data/gridded/data.gpcp.html

**\[S7\] NASA / NOAA catalogue -- GPCP V3.2 status --** V3.2 has been
superseded by V3.3; supports explicit version tracking.
https://data.nasa.gov/dataset/gpcp-precipitation-level-3-monthly-0-5-degree-v3-2-gpcpmon-at-ges-disc-5d4c3

**\[S8\] NOAA NCEI -- OISST product overview --** NOAA OISST v2.1: daily
0.25° global SST from 1 September 1981 to present; update context.
https://www.ncei.noaa.gov/products/optimum-interpolation-sst

**\[S9\] NASA GLDAS V2.0 monthly 0.25° product --** GLDAS-2.0 product
coverage 1948--2014 and product description.
https://data.nasa.gov/dataset/gldas-noah-land-surface-model-l4-monthly-0-25-x-0-25-degree-v2-0-gldas-noah025-m-at-ges-di-6371a

**\[S10\] NASA GLDAS V2.1 monthly 0.25° product --** GLDAS-2.1 from 2000
onward; distinguish main and early production streams.
https://data.nasa.gov/dataset/gldas-noah-land-surface-model-l4-monthly-0-25-x-0-25-degree-v2-1-gldas-noah025-m-at-ges-di-23acd

**\[S11\] NASA GES DISC -- GLDAS README --** GLDAS product families,
spatial resolution, temporal resolution, coverage and model
distinctions.
https://hydro1.gesdisc.eosdis.nasa.gov/data/GLDAS/GLDAS_NOAH025_3H.2.0/doc/README_GLDAS2.pdf

**\[S12\] NASA CMR Search API documentation --** Collection/granule
search, spatial/time queries and granule timeline availability.
https://cmr.earthdata.nasa.gov/search/site/docs/search/api.html

**\[S13\] NASA Harmony documentation --** Supported
spatial/temporal/variable subsetting and service capabilities; check per
collection. https://harmony.earthdata.nasa.gov/docs

**\[S14\] NASA Earthdata -- GIBS --** GIBS imagery browse services and
supported map service protocols. https://earthdata.nasa.gov/gibs

**\[S15\] NASA Worldview --** Example of a GIBS-powered interactive
Earth imagery viewer. https://worldview.earthdata.nasa.gov/

**\[S16\] NOAA CDR / GPCP V3.3 metadata --** GPCP V3.3 product coverage
and 0.5° global grid.
https://catalog.data.gov/dataset/noaa-climate-data-record-cdr-of-the-global-precipitation-climatology-project-gpcp-monthly-

# Appendix A -- Short Glossary

  -----------------------------------------------------------------------
  **Term**                            **Meaning**
  ----------------------------------- -----------------------------------
  GeoJSON                             JSON format for geographic
                                      geometries and features.

  NetCDF                              Scientific array/file format
                                      commonly used for multi-dimensional
                                      Earth-science data.

  Zarr                                Chunked array storage format useful
                                      for cloud and parallel access.

  GeoTIFF / COG                       Georeferenced raster format;
                                      Cloud-Optimized GeoTIFF supports
                                      efficient partial reads.

  Reanalysis                          A model-based reconstruction of
                                      historical
                                      atmospheric/environmental
                                      conditions assimilating
                                      observations.

  Spatial resolution                  Size/spacing of grid cells or pixel
                                      dimensions; not the same as
                                      accuracy.

  Temporal resolution                 How frequently
                                      observations/estimates are
                                      represented (hourly, daily, monthly
                                      etc.).

  Fill value                          Special value marking missing or
                                      invalid data.

  Sen's slope                         Robust estimator of monotonic trend
                                      magnitude.

  Mann--Kendall                       Non-parametric test for monotonic
                                      trend.

  FDR                                 False Discovery Rate correction
                                      used when many statistical tests
                                      are conducted.

  Latest observation date             Latest date represented by the data
                                      values, not the date a file or
                                      catalogue record was published.
  -----------------------------------------------------------------------

# Appendix B -- Final product rule

+-----------------------------------------------------------------------+
| **One connected application, not six disconnected mockups**           |
|                                                                       |
| The homepage and five analysis pages must share one analysis session. |
| Every result must be traceable to a specific product version, field,  |
| date range, region geometry and processing method. The prototype      |
| should prioritise a smaller number of fully working scientific paths  |
| over a larger number of decorative, non-functional screens.           |
+=======================================================================+
+-----------------------------------------------------------------------+
