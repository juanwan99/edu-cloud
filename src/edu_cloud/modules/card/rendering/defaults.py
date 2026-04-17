"""内置默认编辑器布局模板 — 从 card_design_config.json["_layout"] 迁移。"""

DEFAULT_EDITOR_LAYOUT = {
    "paper": "A3",
    "config": {
        "examTitle": "2026年春季期中考试",
        "subjectTitle": "数学",
        "titleSize": 16,
        "subtitleSize": 22,
        "titleSpacing": 1,
        "subtitleSpacing": 6,
        "titleGap": 2,
        "subtitleGap": 3,
        "infoHeight": 24,
        "infoPadding": 4,
        "infoRowGap": 4,
        "infoFontSize": 12,
        "infoBorderWidth": 1,
        "nameLineWidth": 35,
        "digitCount": 10,
        "digitBoxSize": 4.5,
        "digitGap": 0.8,
        "barcodeWidthPct": 40,
        "barcodeTitleSize": 12,
        "noticeHeight": 28,
        "noticeLabelWidth": 8,
        "noticeLabelSize": 11,
        "noticeFontSize": 8,
        "exampleWidth": 12,
        "noticeBorderWidth": 1,
        "absentPadding": 1.5,
        "choicePerRow": 15,
        "fillCount": 3,
        "fillScore": 5,
        "fillPerRow": 2,
        "essayCount": 5,
        "paperSize": "A3",
        "zoom": 66,
        "essayConfig": [
            {
                "score": 10
            },
            {
                "score": 10
            },
            {
                "score": 10
            },
            {
                "score": 10
            },
            {
                "score": 10
            }
        ],
        "choiceCount": 11,
        "optionCount": 4
    },
    "sides": [
        {
            "side": "A",
            "columns": [
                {
                    "col": 0,
                    "regions": [
                        {
                            "id": "header",
                            "type": "fixed",
                            "role": "header",
                            "_side": "A",
                            "_col": 0,
                            "_sideIdx": 0
                        },
                        {
                            "id": "info",
                            "type": "fixed",
                            "role": "info",
                            "_side": "A",
                            "_col": 0,
                            "_sideIdx": 0
                        },
                        {
                            "id": "notice",
                            "type": "fixed",
                            "role": "notice",
                            "_side": "A",
                            "_col": 0,
                            "_sideIdx": 0
                        },
                        {
                            "id": "choices",
                            "type": "fixed",
                            "role": "choices",
                            "count": 11,
                            "options": 4,
                            "perRow": 15,
                            "_side": "A",
                            "_col": 0,
                            "_sideIdx": 0
                        },
                        {
                            "id": "fill-12",
                            "type": "fill",
                            "qno": 12,
                            "spaces": 1,
                            "spaceWidth": "100%",
                            "heightRatio": 0.3333333333333333,
                            "_side": "A",
                            "_col": 0,
                            "_sideIdx": 0
                        },
                        {
                            "id": "fill-13",
                            "type": "fill",
                            "qno": 13,
                            "spaces": 1,
                            "spaceWidth": "100%",
                            "heightRatio": 0.3333333333333333,
                            "_side": "A",
                            "_col": 0,
                            "_sideIdx": 0
                        },
                        {
                            "id": "fill-14",
                            "type": "fill",
                            "qno": 14,
                            "spaces": 1,
                            "spaceWidth": "100%",
                            "heightRatio": 0.3333333333333333,
                            "_side": "A",
                            "_col": 0,
                            "_sideIdx": 0
                        }
                    ]
                },
                {
                    "col": 1,
                    "regions": [
                        {
                            "id": "essay-15",
                            "type": "essay",
                            "qno": 15,
                            "score": 10,
                            "subs": [
                                {
                                    "sub": 1,
                                    "blanks": [
                                        {
                                            "w": "100%"
                                        }
                                    ],
                                    "label": "（1）"
                                }
                            ],
                            "heightRatio": 1,
                            "_side": "A",
                            "_col": 1,
                            "_sideIdx": 0
                        }
                    ]
                },
                {
                    "col": 2,
                    "regions": [
                        {
                            "id": "essay-16",
                            "type": "essay",
                            "qno": 16,
                            "score": 10,
                            "subs": [
                                {
                                    "sub": 1,
                                    "blanks": [
                                        {
                                            "w": "100%"
                                        },
                                        {
                                            "w": "100%"
                                        },
                                        {
                                            "w": "100%"
                                        }
                                    ]
                                }
                            ],
                            "heightRatio": 1,
                            "_side": "A",
                            "_col": 2,
                            "_sideIdx": 0
                        }
                    ]
                }
            ]
        },
        {
            "side": "B",
            "columns": [
                {
                    "col": 0,
                    "regions": [
                        {
                            "id": "essay-17",
                            "type": "essay",
                            "qno": 17,
                            "score": 10,
                            "subs": [
                                {
                                    "sub": 1,
                                    "blanks": [
                                        {
                                            "w": "100%"
                                        },
                                        {
                                            "w": "100%"
                                        },
                                        {
                                            "w": "100%"
                                        }
                                    ]
                                }
                            ],
                            "heightRatio": 1,
                            "_side": "B",
                            "_col": 0,
                            "_sideIdx": 1
                        }
                    ]
                },
                {
                    "col": 1,
                    "regions": [
                        {
                            "id": "essay-18",
                            "type": "essay",
                            "qno": 18,
                            "score": 10,
                            "subs": [
                                {
                                    "sub": 1,
                                    "blanks": [
                                        {
                                            "w": "100%"
                                        },
                                        {
                                            "w": "100%"
                                        },
                                        {
                                            "w": "100%"
                                        }
                                    ]
                                }
                            ],
                            "heightRatio": 1,
                            "_side": "B",
                            "_col": 1,
                            "_sideIdx": 1
                        }
                    ]
                },
                {
                    "col": 2,
                    "regions": [
                        {
                            "id": "essay-19",
                            "type": "essay",
                            "qno": 19,
                            "score": 10,
                            "subs": [
                                {
                                    "sub": 1,
                                    "blanks": [
                                        {
                                            "w": "100%"
                                        },
                                        {
                                            "w": "100%"
                                        },
                                        {
                                            "w": "100%"
                                        }
                                    ]
                                }
                            ],
                            "heightRatio": 1,
                            "_side": "B",
                            "_col": 2,
                            "_sideIdx": 1
                        }
                    ]
                }
            ]
        }
    ]
}
