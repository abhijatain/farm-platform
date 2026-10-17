import { useMemo, useState } from "react";
import FieldRasterImage from "./FieldRasterImage";
import { METRIC_CONFIG } from "./farm-map/satellite";
import type {
  CropCycle, Field, SatelliteMetricType, SatelliteObservation, TimelineItem,
} from "../types/api";
import "./FieldJourneyExplorer.css";

/**
 * Real observations only: a graph point and the corresponding coloured map
 * always refer to the same observation ID and metric raster. Never manufacture
 * daily readings or recolour an NDVI image to pass it off as another index.
 */
const MEASUREMENTS: {key:SatelliteMetricType; title:string; explanation:string}[] = [
  {key:"ndvi",title:"Greenery",explanation:"NDVI: vegetation greenness, not a crop-health diagnosis."},
  {key:"ndmi",title:"Moisture",explanation:"NDMI: canopy moisture-sensitive signal, not measured soil water."},
  {key:"ndre",title:"Chlorophyll",explanation:"NDRE: red-edge vegetation signal, not a laboratory nitrogen test."},
  {key:"bsi",title:"Soil exposure",explanation:"BSI: bare-soil and surface exposure signal."},
  {key:"gndvi",title:"Green-band index",explanation:"GNDVI: green-band vegetation response."},
  {key:"evi2",title:"Canopy density",explanation:"EVI2: vegetation response with reduced soil-background sensitivity."},
  {key:"savi",title:"Soil-adjusted",explanation:"SAVI: vegetation index adjusted for exposed soil."},
  {key:"sar_rvi",title:"Radar",explanation:"RVI: canopy and structure-sensitive radar; different passes may not be comparable."},
  {key:"lst_c",title:"Surface temperature",explanation:"Landsat surface temperature in °C, not air temperature."},
];

type ObservationValue = {
  id:string; date:string; source:string; value:number;
  valid:number|null; metric:SatelliteMetricType;
};

function shapePoints(field:Field):string {
  const rings = field.boundary.coordinates;
  const ring = rings[0];
  if (!ring?.length) return "";
  const lngs=ring.map(p=>p[0]),lats=ring.map(p=>p[1]);
  const left=Math.min(...lngs),right=Math.max(...lngs);
  const bottom=Math.min(...lats),top=Math.max(...lats);
  const dx=Math.max(right-left,0.000001),dy=Math.max(top-bottom,0.000001);
  const factor=Math.min(388/dx,198/dy);
  const x0=(420-dx*factor)/2,y0=(230-dy*factor)/2;
  return ring.map(([lng,lat]) =>
    (x0+(lng-left)*factor).toFixed(2)+","+(y0+(top-lat)*factor).toFixed(2)).join(" ");
}
function day(value:string):number {
  return Date.parse(value.slice(0,10)+"T00:00:00Z");
}
function showDate(value:string) {
  return new Date(value.slice(0,10)+"T00:00:00Z").toLocaleDateString("en-IN",
    {day:"2-digit",month:"short",year:"numeric",timeZone:"UTC"});
}
function sourceName(value:string) {
  if (value==="sentinel-1-rtc") return "Sentinel-1 radar";
  if (value==="landsat-c2-l2") return "Landsat thermal";
  return "Sentinel-2 optical";
}
function prettyValue(value:number, metric:SatelliteMetricType) {
  return value.toFixed(metric==="lst_c"?1:3)+(metric==="lst_c"?" °C":"");
}

export default function FieldJourneyExplorer({
  field,cycle,observations,activities,loading,error,
}: {
  field:Field;cycle:CropCycle|null;observations:SatelliteObservation[];
  activities:TimelineItem[];loading:boolean;error:string|null;
}) {
  const [metricType,setMetricType]=useState<SatelliteMetricType>("ndvi");
  const [chosenObservation,setChosenObservation]=useState<string|null>(null);
  const [hoveredObservation,setHoveredObservation]=useState<string|null>(null);
  const measurement = MEASUREMENTS.find(m=>m.key===metricType) ?? MEASUREMENTS[0];
  const eligible = useMemo(() => {
    const begin = cycle?.started_on ?? null;
    const end = cycle?.harvested_on ?? null;
    const data:ObservationValue[]=[];
    for (const observation of observations) {
      if (begin && observation.observed_on < begin) continue;
      if (end && observation.observed_on > end) continue;
      const m = observation.metrics.find(item =>
        item.metric_type===metricType && item.has_raster &&
        (item.valid_pixel_percent == null || item.valid_pixel_percent >= 80));
      if (m && (m.median != null || m.mean != null)) {
        data.push({id:observation.id,date:observation.observed_on,
          source:observation.source,value:m.median ?? m.mean!,
          valid:m.valid_pixel_percent,metric:metricType});
      }
    }
    return data.sort((a,b)=>a.date.localeCompare(b.date) || a.id.localeCompare(b.id));
  },[observations,cycle?.started_on,cycle?.harvested_on,metricType]);

  const selected=eligible.find(item=>item.id===chosenObservation) ?? eligible.at(-1) ?? null;
  const hovered=eligible.find(item=>item.id===hoveredObservation) ?? null;
  const selectedIndex = selected ? eligible.findIndex(item=>item.id===selected.id) : -1;
  function stepObservation(direction:-1|1) {
    const next=eligible[selectedIndex+direction];
    if (next) setChosenObservation(next.id);
  }

  const config=METRIC_CONFIG[metricType];
  const coords=useMemo(()=>shapePoints(field),[field]);
  const start=cycle?day(cycle.started_on):eligible.length?day(eligible[0].date):Date.now();
  const finish=cycle?.harvested_on ? day(cycle.harvested_on) :
    Math.max(Date.now(),eligible.length?day(eligible[eligible.length-1].date):start+86400000);
  const end=Math.max(finish,start+86400000);
  const W=700,H=250,left=46,right=18,top=20,bottom=48;
  const innerW=W-left-right,innerH=H-top-bottom;
  const vals=eligible.map(item=>item.value);
  const rawMin=Math.min(...vals),rawMax=Math.max(...vals);
  const delta=Math.max(rawMax-rawMin,metricType==="lst_c"?0.5:0.02);
  const min=Number.isFinite(rawMin)?rawMin-delta*.12:0;
  const max=Number.isFinite(rawMax)?rawMax+delta*.12:1;
  const x=(date:string)=>left+(day(date)-start)/(end-start)*innerW;
  const y=(value:number)=>top+(max-value)/Math.max(max-min,.00001)*innerH;
  const line=eligible.map((item,index)=>
    (index===0?"M":"L")+x(item.date).toFixed(2)+" "+y(item.value).toFixed(2)).join(" ");
  const ticks=Array.from({length:5},(_,i)=>({
    date:new Date(start+(end-start)*i/4).toISOString().slice(0,10),
    x:left+innerW*i/4,
  }));
  const markers=activities.filter(item => item.crop_cycle_id===cycle?.id &&
      day(item.occurred_at)>=start && day(item.occurred_at)<=end).slice(0,50);

  return <section className="journey-explorer" aria-label="Interactive crop satellite timeline">
    <div className="journey-explorer-heading">
      <div>
        <span className="workspace-eyebrow">CROP MEASUREMENTS THROUGH TIME</span>
        <h3>How your field changed</h3>
        <p>Select a measurement, then click a dot to view the <strong>actual satellite image from that date</strong>.</p>
      </div>
      {cycle && <small>{showDate(cycle.started_on)} – {cycle.harvested_on ? showDate(cycle.harvested_on) : "present"}</small>}
    </div>
    <div className="journey-metric-pills" role="group" aria-label="Satellite measurements">
      {MEASUREMENTS.map(item=><button type="button" key={item.key}
        aria-pressed={metricType===item.key}
        className={metricType===item.key?"active":""}
        onClick={()=>{setMetricType(item.key);setChosenObservation(null);setHoveredObservation(null);}}>
        {item.title}
      </button>)}
    </div>
    <div className="journey-explorer-columns">
      <div className="journey-explorer-chart">
        <div className="journey-explorer-chart-heading">
          <div><strong>{measurement.title}</strong><small>{measurement.explanation}</small></div>
          <div className="journey-chart-value">
            <strong>{selected?prettyValue(selected.value,metricType):"—"}</strong>
            <small>{selected?showDate(selected.date):"No usable date"}</small>
          </div>
        </div>
        {loading ? <p className="journey-explorer-empty">Loading satellite measurements…</p> :
         error ? <p className="journey-explorer-empty" role="alert">{error}</p> :
         eligible.length===0 ? <p className="journey-explorer-empty">No usable {measurement.title.toLowerCase()} raster observations
          {cycle?" during this crop cycle":""}. Other measurements may be available. No values have been estimated.</p> :
        <>
          <div className="journey-chart-scroll">
            <svg role="group" aria-label={measurement.title+" by acquisition date; select a point for its satellite image"}
              viewBox={`0 0 ${W} ${H}`}>
              {[0,1,2,3,4].map(i=><g key={i}>
                <line x1={left} x2={W-right} y1={top+innerH*i/4} y2={top+innerH*i/4}
                  stroke="#e1e9e2" strokeDasharray="4 5" />
                <text x={left-7} y={top+innerH*i/4+3} fontSize="10" textAnchor="end" fill="#667669">
                  {prettyValue(max-(max-min)*i/4,metricType)}
                </text>
              </g>)}
              {ticks.map(t=><text key={t.date} x={t.x} y={H-10} fontSize="10"
                textAnchor="middle" fill="#647467">{showDate(t.date).slice(0,6)}</text>)}
              {markers.map(item=><g key={item.id}>
                <line x1={x(item.occurred_at)} x2={x(item.occurred_at)}
                  y1={top} y2={top+innerH} stroke="#c1984e"
                  strokeWidth="1.4" strokeDasharray="4 4"/>
                <title>{item.activity_type.replace(/_/g," ")} · {showDate(item.occurred_at)}</title>
              </g>)}
              {eligible.length>1 && <path d={line} fill="none" stroke="#218052"
                strokeWidth="2.8" strokeLinejoin="round"/>}
              {selected && <line x1={x(selected.date)} x2={x(selected.date)}
                y1={top} y2={top+innerH} stroke="#197c4a" strokeWidth="1.5" strokeDasharray="3 5"/>}
              {eligible.map(item=><g key={item.id}>
                <circle cx={x(item.date)} cy={y(item.value)}
                  r={selected?.id===item.id?6:4.6}
                  fill={selected?.id===item.id?"#16864a":"white"}
                  stroke="#16864a" strokeWidth="2"/>
                <circle cx={x(item.date)} cy={y(item.value)} r="15"
                  fill="transparent" role="button" tabIndex={0}
                  aria-label={showDate(item.date)+": "+prettyValue(item.value,metricType)+", show map"}
                  onPointerEnter={()=>setHoveredObservation(item.id)}
                  onPointerLeave={()=>setHoveredObservation(null)}
                  onFocus={()=>setHoveredObservation(item.id)}
                  onBlur={()=>setHoveredObservation(null)}
                  onClick={()=>setChosenObservation(item.id)}
                  onKeyDown={e=>{if(e.key==="Enter"||e.key===" "){e.preventDefault();setChosenObservation(item.id);}}}
                  style={{cursor:"pointer"}}>
                  <title>{showDate(item.date)} · {prettyValue(item.value,metricType)} · {sourceName(item.source)}</title>
                </circle>
              </g>)}
            </svg>
          </div>
          <div className="journey-chart-footer">
            <span>{eligible.length} real satellite acquisition{eligible.length===1?"":"s"}</span>
            <span>{hovered?"Point: "+showDate(hovered.date)+" · "+prettyValue(hovered.value,metricType):
              "Tap or click a point to update the map →"}</span>
            {markers.length>0 && <span className="journey-chart-activities">Dashed lines: recorded field activities</span>}
          </div>
        </>}
      </div>
      <aside className="journey-explorer-map">
        <div className="journey-map-heading"><h4>Field boundary · {measurement.title}</h4>
          <span>{selected?showDate(selected.date):"No image"}</span>
        </div>
        {eligible.length>0 && <div className="journey-map-date-picker">
          <button type="button" onClick={()=>stepObservation(-1)} disabled={selectedIndex<=0}
            aria-label="Previous satellite date">‹</button>
          <label><span>Image date</span>
            <select aria-label="Satellite image date" value={selected?.id ?? ""}
              onChange={event=>setChosenObservation(event.target.value)}>
              {eligible.map(item=><option value={item.id} key={item.id}>
                {showDate(item.date)} · {sourceName(item.source)}
              </option>)}
            </select>
          </label>
          <button type="button" onClick={()=>stepObservation(1)}
            disabled={selectedIndex>=eligible.length-1}
            aria-label="Next satellite date">›</button>
        </div>}
        {selected ? <>
          <FieldRasterImage key={selected.id+":"+metricType}
            fieldId={field.id} observationId={selected.id}
            metricType={metricType} points={coords}
            alt={measurement.title+" real satellite raster from "+showDate(selected.date)} />
          <div className="journey-map-legend">
            <span>{metricType==="lst_c"?"Cooler":"Lower"} ({config.displayMin})</span>
            <i style={{background:config.gradient}} />
            <span>{metricType==="lst_c"?"Hotter":"Higher"} ({config.displayMax})</span>
          </div>
          <dl className="journey-map-stats">
            <div><dt>Median</dt><dd>{prettyValue(selected.value,metricType)}</dd></div>
            <div><dt>Valid pixels</dt><dd>{selected.valid==null?"Not reported":selected.valid.toFixed(0)+"%"}</dd></div>
            <div><dt>Satellite</dt><dd>{sourceName(selected.source)}</dd></div>
          </dl>
          <p>{measurement.explanation} Colours use a fixed scale for this index across dates, not an automatic diagnosis.</p>
        </> : <div className="journey-map-no-data">Select a measurement with usable imagery to see the
          field's real satellite pixel colours. No synthetic field map is shown.</div>}
      </aside>
    </div>
  </section>;
}
