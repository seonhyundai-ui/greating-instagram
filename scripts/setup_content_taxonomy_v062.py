from __future__ import annotations

from collections import OrderedDict

from gspread.utils import rowcol_to_a1

from config.settings import (
    GOOGLE_SPREADSHEET_ID,
)

from src.sheets_client import (
    get_gspread_client,
)


VERSION = "0.6.2"

MASTER_SHEET = "CONTENT_MASTER"
TAXONOMY_SHEET = "97_TAXONOMY"

# 앞으로 콘텐츠가 늘어나도 드롭다운이 자동 적용되는 범위
VALIDATION_MAX_ROW = 5000


# ============================================================
# 기본 분류값
# ============================================================

BASE_CATEGORIES = [
    "상품",
    "레시피",
    "이벤트",
    "정보",
    "프로모션",
    "라이프스타일",
    "브랜드",
]


BASE_CREATIVE_FORMATS = [
    "제품 단독",
    "제품 활용",
    "레시피",
    "인물",
    "텍스트 중심",
    "라이프스타일",
    "UGC",
    "기타",
]


CLASSIFICATION_STATUSES = [
    "AI_SEEDED",
    "PENDING",
    "MANUAL_DONE",
    "NEED_REVIEW",
]


# ============================================================
# Helpers
# ============================================================

def clean(value) -> str:

    if value is None:
        return ""

    return str(value).strip()


def unique_keep_order(
    values: list[str],
) -> list[str]:

    seen = OrderedDict()

    for value in values:

        value = clean(value)

        if not value:
            continue

        seen[value] = True

    return list(
        seen.keys()
    )


def merge_unique(
    *groups,
) -> list[str]:

    output = []

    for group in groups:
        output.extend(group)

    return unique_keep_order(
        output
    )


def get_column_values(
    headers: list[str],
    rows: list[list[str]],
    column_name: str,
) -> list[str]:

    if column_name not in headers:
        return []

    index = headers.index(
        column_name
    )

    values = []

    for row in rows:

        padded = (
            list(row)
            + [""] * (
                len(headers)
                - len(row)
            )
        )

        values.append(
            clean(
                padded[index]
            )
        )

    return unique_keep_order(
        values
    )


def get_existing_taxonomy_values(
    worksheet,
    column_index: int,
) -> list[str]:

    values = worksheet.col_values(
        column_index
    )

    if values:
        values = values[1:]

    return unique_keep_order(
        values
    )


# ============================================================
# Main
# ============================================================

def main() -> None:

    print("=" * 82)
    print(
        "Greating Instagram "
        f"Content Taxonomy Setup v{VERSION}"
    )
    print("=" * 82)

    client = get_gspread_client()

    spreadsheet = client.open_by_key(
        GOOGLE_SPREADSHEET_ID
    )

    # ========================================================
    # 1. CONTENT_MASTER
    # ========================================================

    print()
    print(
        "[1/5] Load CONTENT_MASTER"
    )

    master_ws = spreadsheet.worksheet(
        MASTER_SHEET
    )

    values = master_ws.get_all_values()

    if not values:
        raise RuntimeError(
            "CONTENT_MASTER is empty."
        )

    headers = list(
        values[0]
    )

    rows = [
        list(row)
        for row in values[1:]
    ]

    print(
        f"      rows={len(rows):,}"
        f" | columns={len(headers):,}"
    )

    # ========================================================
    # 2. ai_status -> classification_status
    # ========================================================

    print()
    print(
        "[2/5] Migrate classification status"
    )

    if (
        "classification_status"
        in headers
    ):

        status_col_index = (
            headers.index(
                "classification_status"
            )
            + 1
        )

        print(
            "      classification_status "
            "already exists"
        )

    elif "ai_status" in headers:

        status_col_index = (
            headers.index(
                "ai_status"
            )
            + 1
        )

        master_ws.update_cell(
            1,
            status_col_index,
            "classification_status",
        )

        headers[
            status_col_index - 1
        ] = "classification_status"

        print(
            "      ai_status "
            "-> classification_status"
        )

    else:

        new_col_index = (
            len(headers)
            + 1
        )

        if (
            master_ws.col_count
            < new_col_index
        ):

            master_ws.resize(
                cols=new_col_index
            )

        master_ws.update_cell(
            1,
            new_col_index,
            "classification_status",
        )

        headers.append(
            "classification_status"
        )

        status_col_index = (
            new_col_index
        )

        print(
            "      classification_status "
            f"added at col={status_col_index}"
        )

    # --------------------------------------------------------
    # 현재 상태값 다시 읽기
    # --------------------------------------------------------

    current_status_values = (
        master_ws.col_values(
            status_col_index
        )
    )

    ai_title_index = None

    if "ai_title" in headers:

        ai_title_index = (
            headers.index(
                "ai_title"
            )
        )

    converted_statuses = []

    ai_seeded_count = 0
    pending_count = 0
    manual_count = 0
    review_count = 0

    for row_number, raw_row in enumerate(
        rows,
        start=2,
    ):

        padded = (
            raw_row
            + [""] * (
                len(headers)
                - len(raw_row)
            )
        )

        old_status = ""

        status_list_index = (
            row_number - 1
        )

        if (
            status_list_index
            < len(
                current_status_values
            )
        ):

            old_status = clean(
                current_status_values[
                    status_list_index
                ]
            )

        normalized = (
            old_status.upper()
        )

        ai_title = ""

        if (
            ai_title_index
            is not None
            and ai_title_index
            < len(padded)
        ):

            ai_title = clean(
                padded[
                    ai_title_index
                ]
            )

        # ------------------------------------
        # 기존 AI 결과
        # ------------------------------------

        if normalized in (
            "OK",
            "AI_SEEDED",
        ):

            new_status = (
                "AI_SEEDED"
            )

            ai_seeded_count += 1

        # ------------------------------------
        # 신규 미분류
        # ------------------------------------

        elif normalized in (
            "",
            "PENDING",
        ):

            if ai_title:

                new_status = (
                    "AI_SEEDED"
                )

                ai_seeded_count += 1

            else:

                new_status = (
                    "PENDING"
                )

                pending_count += 1

        # ------------------------------------
        # 수동 완료
        # ------------------------------------

        elif normalized == "MANUAL_DONE":

            new_status = (
                "MANUAL_DONE"
            )

            manual_count += 1

        # ------------------------------------
        # 검토 필요
        # ------------------------------------

        elif normalized == "NEED_REVIEW":

            new_status = (
                "NEED_REVIEW"
            )

            review_count += 1

        # ------------------------------------
        # 알 수 없는 기존 값은 그대로 유지
        # ------------------------------------

        else:

            new_status = (
                old_status
            )

        converted_statuses.append(
            [new_status]
        )

    status_start_cell = (
        rowcol_to_a1(
            1,
            status_col_index,
        )
    )

    master_ws.update(
        range_name=status_start_cell,
        values=[
            [
                "classification_status"
            ],
            *converted_statuses,
        ],
        value_input_option="RAW",
    )

    print(
        f"      AI_SEEDED="
        f"{ai_seeded_count:,}"
        f" | PENDING="
        f"{pending_count:,}"
        f" | MANUAL_DONE="
        f"{manual_count:,}"
        f" | NEED_REVIEW="
        f"{review_count:,}"
    )

    # ========================================================
    # 3. 현재 AI 분류값에서 taxonomy 추출
    # ========================================================

    print()
    print(
        "[3/5] Build taxonomy from existing AI classifications"
    )

    existing_categories = (
        get_column_values(
            headers,
            rows,
            "content_category",
        )
    )

    existing_subcategories = (
        get_column_values(
            headers,
            rows,
            "content_subcategory",
        )
    )

    existing_formats = (
        get_column_values(
            headers,
            rows,
            "creative_format",
        )
    )

    categories = merge_unique(
        BASE_CATEGORIES,
        existing_categories,
    )

    creative_formats = merge_unique(
        BASE_CREATIVE_FORMATS,
        existing_formats,
    )

    subcategories = (
        existing_subcategories
    )

    # ========================================================
    # 4. 97_TAXONOMY 생성/갱신
    # ========================================================

    print()
    print(
        "[4/5] Create / update 97_TAXONOMY"
    )

    sheet_names = {
        worksheet.title
        for worksheet
        in spreadsheet.worksheets()
    }

    if (
        TAXONOMY_SHEET
        in sheet_names
    ):

        taxonomy_ws = (
            spreadsheet.worksheet(
                TAXONOMY_SHEET
            )
        )

        # 담당자가 기존 Taxonomy에 직접 추가한 값도 보존
        old_categories = (
            get_existing_taxonomy_values(
                taxonomy_ws,
                1,
            )
        )

        old_formats = (
            get_existing_taxonomy_values(
                taxonomy_ws,
                2,
            )
        )

        old_subcategories = (
            get_existing_taxonomy_values(
                taxonomy_ws,
                3,
            )
        )

        categories = merge_unique(
            categories,
            old_categories,
        )

        creative_formats = (
            merge_unique(
                creative_formats,
                old_formats,
            )
        )

        subcategories = merge_unique(
            subcategories,
            old_subcategories,
        )

        print(
            "      existing taxonomy merged"
        )

    else:

        taxonomy_ws = (
            spreadsheet.add_worksheet(
                title=TAXONOMY_SHEET,
                rows=500,
                cols=4,
            )
        )

        print(
            "      [CREATE] "
            f"{TAXONOMY_SHEET}"
        )

    # 최소 4열 보장
    if taxonomy_ws.col_count < 4:

        taxonomy_ws.resize(
            cols=4
        )

    max_length = max(
        len(categories),
        len(creative_formats),
        len(subcategories),
        len(
            CLASSIFICATION_STATUSES
        ),
    )

    taxonomy_matrix = [
        [
            "content_category",
            "creative_format",
            "content_subcategory",
            "classification_status",
        ]
    ]

    for index in range(
        max_length
    ):

        taxonomy_matrix.append(
            [
                (
                    categories[index]
                    if index
                    < len(categories)
                    else ""
                ),
                (
                    creative_formats[index]
                    if index
                    < len(
                        creative_formats
                    )
                    else ""
                ),
                (
                    subcategories[index]
                    if index
                    < len(subcategories)
                    else ""
                ),
                (
                    CLASSIFICATION_STATUSES[
                        index
                    ]
                    if index
                    < len(
                        CLASSIFICATION_STATUSES
                    )
                    else ""
                ),
            ]
        )

    required_taxonomy_rows = max(
        len(
            taxonomy_matrix
        ) + 50,
        500,
    )

    if (
        taxonomy_ws.row_count
        < required_taxonomy_rows
    ):

        taxonomy_ws.resize(
            rows=required_taxonomy_rows,
            cols=max(
                taxonomy_ws.col_count,
                4,
            ),
        )

    taxonomy_ws.clear()

    taxonomy_ws.update(
        range_name="A1",
        values=taxonomy_matrix,
        value_input_option="RAW",
    )

    taxonomy_ws.freeze(
        rows=1
    )

    print(
        f"      content_category="
        f"{len(categories):,}"
    )

    print(
        f"      creative_format="
        f"{len(creative_formats):,}"
    )

    print(
        f"      content_subcategory="
        f"{len(subcategories):,}"
    )

    # ========================================================
    # 5. CONTENT_MASTER dropdown
    # ========================================================

    print()
    print(
        "[5/5] Apply dropdown validation"
    )

    # 앞으로 들어올 신규 콘텐츠까지 드롭다운 적용
    if (
        master_ws.row_count
        < VALIDATION_MAX_ROW
    ):

        master_ws.resize(
            rows=VALIDATION_MAX_ROW,
            cols=max(
                master_ws.col_count,
                len(headers),
            ),
        )

    master_sheet_id = (
        master_ws.id
    )

    validation_specs = [
        {
            "column": (
                "content_category"
            ),
            "taxonomy_col": "A",
            "count": len(categories),
        },
        {
            "column": (
                "creative_format"
            ),
            "taxonomy_col": "B",
            "count": len(
                creative_formats
            ),
        },
        {
            "column": (
                "content_subcategory"
            ),
            "taxonomy_col": "C",
            "count": len(
                subcategories
            ),
        },
        {
            "column": (
                "classification_status"
            ),
            "taxonomy_col": "D",
            "count": len(
                CLASSIFICATION_STATUSES
            ),
        },
    ]

    requests = []

    for spec in validation_specs:

        column_name = (
            spec["column"]
        )

        if column_name not in headers:

            print(
                f"      [SKIP] "
                f"{column_name} missing"
            )

            continue

        column_index = (
            headers.index(
                column_name
            )
        )

        taxonomy_end_row = (
            spec["count"]
            + 1
        )

        taxonomy_range = (
            f"='{TAXONOMY_SHEET}'!"
            f"${spec['taxonomy_col']}$2:"
            f"${spec['taxonomy_col']}"
            f"${taxonomy_end_row}"
        )

        requests.append(
            {
                "setDataValidation": {
                    "range": {
                        "sheetId": (
                            master_sheet_id
                        ),
                        "startRowIndex": 1,
                        "endRowIndex": (
                            VALIDATION_MAX_ROW
                        ),
                        "startColumnIndex": (
                            column_index
                        ),
                        "endColumnIndex": (
                            column_index
                            + 1
                        ),
                    },
                    "rule": {
                        "condition": {
                            "type": (
                                "ONE_OF_RANGE"
                            ),
                            "values": [
                                {
                                    "userEnteredValue": (
                                        taxonomy_range
                                    )
                                }
                            ],
                        },
                        "strict": True,
                        "showCustomUi": True,
                    },
                }
            }
        )

    if requests:

        spreadsheet.batch_update(
            {
                "requests": requests
            }
        )

    print(
        "      content_category "
        "dropdown OK"
    )

    print(
        "      content_subcategory "
        "dropdown OK"
    )

    print(
        "      creative_format "
        "dropdown OK"
    )

    print(
        "      classification_status "
        "dropdown OK"
    )

    print()
    print("=" * 82)
    print(
        "CONTENT TAXONOMY SETUP COMPLETED "
        f"| VERSION={VERSION}"
    )
    print("=" * 82)


if __name__ == "__main__":
    main()