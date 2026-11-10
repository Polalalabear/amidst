// Test support only. Compact reproduction of the Office `synchronized_evidence` DTO returned by the local workbench service
// (scene blender-office, cameras FRONT+REAR, 0–9.8 s, 61 samples, source HEAD 57eab7e). Positions, observation refs, camera ids,
// connect_from_previous flags and missing intervals are copied unchanged; candidate/camera membership is stored once per row phase.
const F='CAM_1F_AUDITORIUM_FRONT',R='CAM_1F_AUDITORIUM_REAR';
const C={a:'candidate:5dfa938ca65903731eb93aac',b:'candidate:c47e4d3c8912b420011d76d0',c:'candidate:3dc46ee27172586510fc0765',d:'candidate:5b4e7cddf4fe74feb7b2e4f0'};
// Each observation is emitted once per candidate group, which is how the backend reports one source observation per path.
const PHASES={
  p0:[[[F],[C.a,C.b,C.c,C.d]]],
  p1:[[[F,R],[C.c]],[[F],[C.a,C.b,C.d]]],
  p2:[[[F],[C.b,C.c,C.d]],[[F,R],[C.a]]],
  p3:[[[F,R],[C.b]],[[F],[C.a,C.c,C.d]]],
  p4:[[[R],[C.d]],[[F,R],[C.a,C.b,C.c]]]
};
const ZA=0.49594758987426735,ZB=0.4959475898742678;
// [timestamp, observation id, connect_from_previous, camera, x, y, z, phase]
const OBSERVATIONS=[
  [0,'93bb707f303fb71fc85a8bcd',0,F,34.400553233615646,48.10290154951064,ZA,'p0'],
  [0.2,'978c0e030f39526d9836e070',1,F,34.3377863795099,48.14701356270521,ZA,'p0'],
  [0.4,'b8177d3641ac41fe8c5a3314',1,F,34.285480667483995,48.18377357389123,ZB,'p0'],
  [0.6,'ac7d7d63cc97466e19153d39',0,F,32.78292744495016,47.38263825182045,ZB,'p1'],
  [0.8,'9692a7c226f755182fa178bf',1,F,32.573190120635616,47.345378202105984,ZB,'p1'],
  [1,'2207449e6d785ae61dbc9c2f',1,F,32.50453695714771,47.39362705734096,ZB,'p1'],
  [1.2,'2252b0e914ef1ff2a8f83402',1,F,32.279422527351144,47.3642648948852,0.49594758987426824,'p1'],
  [1.4,'4e12f2cab0a97b0588a7751a',1,F,32.062357548790686,47.32626735193742,ZA,'p1'],
  [1.6,'796f9ea825430c556b115b98',1,F,31.992614290854572,47.37528231502523,ZB,'p1'],
  [1.8,'2df3c1874e209639bf7dc156',1,F,31.911247156041924,47.43246643901692,ZB,'p1'],
  [2,'78d9e0341de5de450fd75847',0,F,33.607947205725665,48.503259117569954,ZB,'p2'],
  [2.2,'a930d37e7c8362eb4f447455',1,F,34.26042794385201,48.95235089477476,ZB,'p2'],
  [2.4,'4bd420d4445fbc90b79147d3',1,F,34.30377270041956,49.065908548854885,ZB,'p2'],
  [2.6,'7b0c95680aa4797e81169605',1,F,34.35649041824195,49.17091895616186,ZB,'p2'],
  [2.8,'e775b180466c37db887b4cd9',1,F,34.3166390090866,49.1989261906868,ZB,'p2'],
  [3,'47765d8f3ea0dd23ae0639f2',1,F,34.37880898426998,49.29537336368918,ZB,'p2'],
  [3.2,'dcb483c54409676f61c12851',1,F,34.3194358831329,49.33710027920359,ZB,'p2'],
  [3.4,'7f1d899022b521c4b09e5b99',1,F,34.35168246138648,49.45269577021121,ZB,'p2'],
  [3.6,'e5bd64f6afb76f32512c32d1',1,F,34.2828788625675,49.501050360513304,ZB,'p2'],
  [3.8,'1ea9b7deac157964c0f29f3b',1,F,34.34444480572337,49.5941964975214,ZB,'p2'],
  [4,'5af5000a8120938a5a6ed937',1,F,34.41489394492998,49.67929229217611,ZB,'p2'],
  [4.2,'edd2e36fd7e3ea0b6c785236',1,F,34.38579735540381,49.69974113081706,ZB,'p2'],
  [4.4,'fe656e1bf939570f51f9ca73',0,F,30.556454626638597,47.79435970859536,ZB,'p3'],
  [4.4,'add9f687d311742321e80dff',1,F,34.579774617470896,49.56341554088987,ZB,'p2'],
  [8.6,'997166541f223b4f923d8bff',0,R,31.544060670130392,53.648921062762426,ZA,'p4'],
  [8.8,'5fcdf527b0a1b893707c66d2',1,R,31.741093856643598,53.508820977812796,ZA,'p4'],
  [9,'1520dbf1c3812404a6cd00e7',1,R,31.962123348471412,53.39053970623486,ZA,'p4'],
  [9.2,'72a7d5c5ae35b93a8bd2dc5b',1,R,32.165310891462084,53.2649607543041,ZA,'p4'],
  [9.4,'87fea74631c15319123be327',1,R,32.220200759348884,53.30296944033114,ZB,'p4'],
  [9.6,'cf3d851558ff4fb8397ae6bc',1,R,32.28881309455038,53.35048029810245,ZA,'p4'],
  [9.8,'a3dca6d722479a39173a68fc',1,R,32.35742543013298,53.39799115613766,ZA,'p4']
];

export const OFFICE_CAMERAS=[F,R];
export const OFFICE_CANDIDATES=C;
export const OFFICE_GAPS=[
  {time_range:[4.4,8.6],camera_ids:[F,R],candidate_ref:C.a,reason:'CROSS_CAMERA_LONG_GAP',state:'MISSING'},
  {time_range:[4.4,8.6],camera_ids:[F,R],candidate_ref:C.b,reason:'CROSS_CAMERA_LONG_GAP',state:'MISSING'},
  {time_range:[1.8,8.6],camera_ids:[F,R],candidate_ref:C.c,reason:'CROSS_CAMERA_LONG_GAP',state:'MISSING'}
];
export function officeSamples() {
  const rows=[];
  for(const [timestamp,id,connect,camera,x,y,z,phase] of OBSERVATIONS){
    for(const [sources,candidates] of PHASES[phase])rows.push({timestamp,world_position:[x,y,z],state:'PROJECTED_OBSERVATION',camera_id:camera,
      observation_ref:`observation:${id}`,connect_from_previous:connect===1,source_camera_ids:[...sources],candidate_refs:[...candidates],missing_reason:null});
    if(timestamp===4.4&&id==='add9f687d311742321e80dff'){
      rows.push({timestamp:5.2,world_position:null,state:'MISSING',camera_id:null,observation_ref:null,connect_from_previous:false,source_camera_ids:[F,R],candidate_refs:[C.c],missing_reason:'CROSS_CAMERA_LONG_GAP'},
        {timestamp:6.5,world_position:null,state:'MISSING',camera_id:null,observation_ref:null,connect_from_previous:false,source_camera_ids:[F,R],candidate_refs:[C.a,C.b],missing_reason:'CROSS_CAMERA_LONG_GAP'});
    }
  }
  return rows;
}
export const OFFICE_SOURCE_SHA='a'.repeat(64);
// A structurally valid review response around the Office evidence (only the fields the frontend validator and scene plan read).
export function officeReviewResult() {
  const ref=(prefix,n)=>prefix+':'+String(n).padStart(24,'0');
  return {schema_version:'workbench.blender-physical-review.v1',review_sha256:'b'.repeat(64),
    source_binding:{source_sha256:OFFICE_SOURCE_SHA,site_id:'office',run_id:'run-A',clock_id:'source-clock',dataset_sha256:'d'.repeat(64)},
    source_sha256:OFFICE_SOURCE_SHA,physical_source_sha256:'c'.repeat(64),evidence_hashes:{geometry_archive:'f'.repeat(64)},
    selection:{camera_ids:[...OFFICE_CAMERAS],time_range:[0,9.8],clock_id:'source-clock',canonical_ranking_scope:'FULL_SOURCE_UNCHANGED'},
    prior_results:{checkpoint:'2de9821',status:'UNCHANGED_PRIOR_RESULTS',media_rerendered:false,ranking_recomputed:false},
    review_state:{revision:0,records:[],rerun_authorized:false},agent_used:false,formal_acceptance:false,
    items:[{item_ref:ref('review-item',1),kind:'PORTAL_APERTURE',title:'Office portal',site_id:'office',status:'UNKNOWN',review_status:'PENDING',source_authority:'HUMAN_REVIEW',
      geometry_refs:[ref('review-geometry',1)],evidence_refs:['evidence:geometry_archive'],pending_gaps:[{code:'MISSING_APERTURE',description:'pending'}],ownership_confirmed:false,
      checklist:[{check_ref:ref('review-check',1),title:'check',required_evidence:['evidence:geometry_archive'],default_decision:'UNKNOWN'}],
      focus:{camera_ids:[...OFFICE_CAMERAS],time_range:[0,9.8],geometry_refs:[ref('review-geometry',1)]}}],
    geometry_primitives:[{geometry_ref:ref('review-geometry',1),kind:'SOURCE_ANNOTATION',label:'annotation',units:'METRES',vertices:[[30,47,.5],[31,47,.5],[31,48,2.5]],triangles:[[0,1,2]],
      authority:'HUMAN_REVIEW',display_only:true,is_aperture:false,is_collider:false,truncated:false}],
    synchronized_evidence:{samples:officeSamples(),missing_intervals:structuredClone(OFFICE_GAPS),sample_count:61,maximum_samples:400,truncated:false}};
}
