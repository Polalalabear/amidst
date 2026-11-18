// Route plans only (no answers) for the scripted operator, copied from configs/evaluation/live_hardset_v1.json
// (cases with source GENERATED, route_plan.start_xy/steps). test/script_operator.test.mjs keeps the two equal.
export const HARDSET_ROUTES = Object.freeze({
 "H1-1": {
  "run_id": "A4-1",
  "start_xy": [
   -10,
   -0.4
  ],
  "steps": [
   {
    "mode": "hold",
    "seconds": 3
   },
   {
    "mode": "hold_until",
    "t_s": 6
   },
   {
    "mode": "walk",
    "to_xy": [
     -3.35,
     -0.25
    ]
   },
   {
    "mode": "walk",
    "to_xy": [
     0.35,
     1.1
    ]
   },
   {
    "mode": "walk",
    "to_xy": [
     7.0,
     1.1
    ]
   },
   {
    "mode": "hold_until",
    "t_s": 21.5
   },
   {
    "mode": "walk",
    "to_xy": [
     8.0,
     0.6
    ]
   },
   {
    "mode": "walk",
    "to_xy": [
     8.0,
     -0.6
    ]
   },
   {
    "mode": "walk",
    "to_xy": [
     9.0,
     -3.0
    ]
   },
   {
    "mode": "walk",
    "to_xy": [
     9.75,
     -4.5
    ]
   },
   {
    "mode": "hold",
    "seconds": 20
   },
   {
    "mode": "run",
    "to_xy": [
     9.0,
     -3.0
    ]
   },
   {
    "mode": "run",
    "to_xy": [
     8.0,
     -0.6
    ]
   },
   {
    "mode": "run",
    "to_xy": [
     8.0,
     0.6
    ]
   },
   {
    "mode": "run",
    "to_xy": [
     9.5,
     1.1
    ]
   },
   {
    "mode": "run",
    "to_xy": [
     13.0,
     1.1
    ]
   },
   {
    "mode": "run",
    "to_xy": [
     14.0,
     1.1
    ]
   },
   {
    "mode": "run",
    "to_xy": [
     16.4,
     0.8
    ]
   },
   {
    "mode": "hold",
    "seconds": 8
   }
  ]
 },
 "H1-2": {
  "run_id": "A4-1",
  "start_xy": [
   -10,
   -0.4
  ],
  "steps": [
   {
    "mode": "hold",
    "seconds": 3
   },
   {
    "mode": "hold_until",
    "t_s": 4.5
   },
   {
    "mode": "walk",
    "to_xy": [
     -8.5,
     3.1
    ]
   },
   {
    "mode": "walk",
    "to_xy": [
     -12.75,
     6.0
    ]
   },
   {
    "mode": "hold_until",
    "t_s": 27.0
   },
   {
    "mode": "run",
    "to_xy": [
     -11.5,
     3.0
    ]
   },
   {
    "mode": "run",
    "to_xy": [
     -10.0,
     -0.4
    ]
   },
   {
    "mode": "run",
    "to_xy": [
     -3.35,
     -0.25
    ]
   },
   {
    "mode": "walk",
    "to_xy": [
     0.35,
     1.1
    ]
   },
   {
    "mode": "hold",
    "seconds": 6
   }
  ]
 },
 "H1-3": {
  "run_id": "B4-1",
  "start_xy": [
   4,
   1
  ],
  "steps": [
   {
    "mode": "hold",
    "seconds": 3
   },
   {
    "mode": "walk",
    "to_xy": [
     8.0,
     0.6
    ]
   },
   {
    "mode": "walk",
    "to_xy": [
     8.0,
     -0.6
    ]
   },
   {
    "mode": "walk",
    "to_xy": [
     8.0,
     -2.0
    ]
   },
   {
    "mode": "hold_until",
    "t_s": 18.0
   },
   {
    "mode": "walk",
    "to_xy": [
     8.0,
     -0.6
    ]
   },
   {
    "mode": "walk",
    "to_xy": [
     8.0,
     0.6
    ]
   },
   {
    "mode": "walk",
    "to_xy": [
     5.0,
     1.0
    ]
   },
   {
    "mode": "walk",
    "to_xy": [
     3.4,
     0.5
    ]
   },
   {
    "mode": "walk",
    "to_xy": [
     2.0,
     -1.35
    ]
   },
   {
    "mode": "hold",
    "seconds": 15
   },
   {
    "mode": "walk",
    "to_xy": [
     3.4,
     0.5
    ]
   },
   {
    "mode": "run",
    "to_xy": [
     8.0,
     1.25
    ]
   },
   {
    "mode": "run",
    "to_xy": [
     11.4,
     1.3
    ]
   },
   {
    "mode": "run",
    "to_xy": [
     14.1,
     1.1
    ]
   },
   {
    "mode": "run",
    "to_xy": [
     15.5,
     1.1
    ]
   },
   {
    "mode": "hold",
    "seconds": 8
   }
  ]
 },
 "H4-1": {
  "run_id": "A4-1",
  "start_xy": [
   -10,
   -0.4
  ],
  "steps": [
   {
    "mode": "hold",
    "seconds": 3
   },
   {
    "mode": "run",
    "to_xy": [
     -3.35,
     -0.25
    ]
   },
   {
    "mode": "run",
    "to_xy": [
     0.35,
     0.6
    ]
   },
   {
    "mode": "run",
    "to_xy": [
     8.0,
     0.6
    ]
   },
   {
    "mode": "run",
    "to_xy": [
     8.0,
     -0.6
    ]
   },
   {
    "mode": "run",
    "to_xy": [
     8.0,
     -1.6
    ]
   },
   {
    "mode": "hold_until",
    "t_s": 14.0
   },
   {
    "mode": "walk",
    "to_xy": [
     8.0,
     -0.6
    ]
   },
   {
    "mode": "walk",
    "to_xy": [
     8.0,
     0.6
    ]
   },
   {
    "mode": "walk",
    "to_xy": [
     9.5,
     1.1
    ]
   },
   {
    "mode": "walk",
    "to_xy": [
     11.0,
     1.1
    ]
   },
   {
    "mode": "hold",
    "seconds": 2
   }
  ]
 },
 "H4-2": {
  "run_id": "B4-1",
  "start_xy": [
   4,
   1
  ],
  "steps": [
   {
    "mode": "hold",
    "seconds": 3
   },
   {
    "mode": "walk",
    "to_xy": [
     8.0,
     0.6
    ]
   },
   {
    "mode": "walk",
    "to_xy": [
     8.0,
     -0.6
    ]
   },
   {
    "mode": "walk",
    "to_xy": [
     8.0,
     -2.0
    ]
   },
   {
    "mode": "hold_until",
    "t_s": 14.0
   },
   {
    "mode": "run",
    "to_xy": [
     8.0,
     0.6
    ]
   },
   {
    "mode": "run",
    "to_xy": [
     11.4,
     1.3
    ]
   },
   {
    "mode": "run",
    "to_xy": [
     15.0,
     1.1
    ]
   },
   {
    "mode": "run",
    "to_xy": [
     16.4,
     0.8
    ]
   },
   {
    "mode": "hold",
    "seconds": 6
   }
  ]
 },
 "H4-3": {
  "run_id": "B4-1",
  "start_xy": [
   4,
   1
  ],
  "steps": [
   {
    "mode": "hold",
    "seconds": 3
   },
   {
    "mode": "walk",
    "to_xy": [
     8.0,
     0.6
    ]
   },
   {
    "mode": "walk",
    "to_xy": [
     8.0,
     -0.6
    ]
   },
   {
    "mode": "walk",
    "to_xy": [
     8.0,
     -2.0
    ]
   },
   {
    "mode": "hold_until",
    "t_s": 27.0
   },
   {
    "mode": "walk",
    "to_xy": [
     8.0,
     -0.6
    ]
   },
   {
    "mode": "walk",
    "to_xy": [
     8.0,
     0.6
    ]
   },
   {
    "mode": "walk",
    "to_xy": [
     11.4,
     1.3
    ]
   },
   {
    "mode": "hold_until",
    "t_s": 33.0
   },
   {
    "mode": "walk",
    "to_xy": [
     14.1,
     1.1
    ]
   },
   {
    "mode": "walk",
    "to_xy": [
     15.5,
     1.1
    ]
   },
   {
    "mode": "hold_until",
    "t_s": 40.0
   },
   {
    "mode": "walk",
    "to_xy": [
     16.7,
     1.8
    ]
   },
   {
    "mode": "walk",
    "to_xy": [
     16.7,
     9.0
    ]
   },
   {
    "mode": "hold",
    "seconds": 5
   },
   {
    "mode": "walk",
    "to_xy": [
     16.7,
     3.0
    ]
   }
  ]
 },
 "H5-1": {
  "run_id": "A4-1",
  "start_xy": [
   -10,
   -0.4
  ],
  "steps": [
   {
    "mode": "hold",
    "seconds": 3
   },
   {
    "mode": "walk",
    "to_xy": [
     -3.35,
     -0.25
    ]
   },
   {
    "mode": "walk",
    "to_xy": [
     0.35,
     1.1
    ]
   },
   {
    "mode": "walk",
    "to_xy": [
     3.4,
     0.5
    ]
   },
   {
    "mode": "walk",
    "to_xy": [
     2.0,
     -1.35
    ]
   },
   {
    "mode": "hold",
    "seconds": 15
   },
   {
    "mode": "walk",
    "to_xy": [
     3.4,
     0.5
    ]
   },
   {
    "mode": "walk",
    "to_xy": [
     5.0,
     1.1
    ]
   },
   {
    "mode": "hold",
    "seconds": 5
   }
  ]
 },
 "H5-2": {
  "run_id": "A4-1",
  "start_xy": [
   -10,
   -0.4
  ],
  "steps": [
   {
    "mode": "hold",
    "seconds": 3
   },
   {
    "mode": "walk",
    "to_xy": [
     -3.35,
     -0.25
    ]
   },
   {
    "mode": "walk",
    "to_xy": [
     0.35,
     1.1
    ]
   },
   {
    "mode": "walk",
    "to_xy": [
     3.4,
     0.5
    ]
   },
   {
    "mode": "walk",
    "to_xy": [
     2.0,
     -1.35
    ]
   },
   {
    "mode": "hold",
    "seconds": 15
   },
   {
    "mode": "walk",
    "to_xy": [
     3.4,
     0.5
    ]
   },
   {
    "mode": "walk",
    "to_xy": [
     0.35,
     1.1
    ]
   },
   {
    "mode": "walk",
    "to_xy": [
     -3.35,
     -0.25
    ]
   },
   {
    "mode": "walk",
    "to_xy": [
     -8.0,
     -0.4
    ]
   },
   {
    "mode": "hold",
    "seconds": 5
   }
  ]
 },
 "H5-3": {
  "run_id": "B4-1",
  "start_xy": [
   4,
   1
  ],
  "steps": [
   {
    "mode": "hold",
    "seconds": 3
   },
   {
    "mode": "walk",
    "to_xy": [
     8.0,
     0.6
    ]
   },
   {
    "mode": "walk",
    "to_xy": [
     8.0,
     -0.6
    ]
   },
   {
    "mode": "walk",
    "to_xy": [
     8.0,
     -2.0
    ]
   },
   {
    "mode": "hold_until",
    "t_s": 21.0
   },
   {
    "mode": "walk",
    "to_xy": [
     8.0,
     -0.6
    ]
   },
   {
    "mode": "walk",
    "to_xy": [
     8.0,
     0.6
    ]
   },
   {
    "mode": "walk",
    "to_xy": [
     11.4,
     1.3
    ]
   },
   {
    "mode": "walk",
    "to_xy": [
     13.0,
     1.1
    ]
   },
   {
    "mode": "walk",
    "to_xy": [
     14.0,
     1.1
    ]
   },
   {
    "mode": "walk",
    "to_xy": [
     13.75,
     0.5
    ]
   },
   {
    "mode": "hold",
    "seconds": 10
   },
   {
    "mode": "walk",
    "to_xy": [
     14.1,
     1.1
    ]
   },
   {
    "mode": "walk",
    "to_xy": [
     11.4,
     1.3
    ]
   },
   {
    "mode": "hold",
    "seconds": 3
   }
  ]
 }
});
