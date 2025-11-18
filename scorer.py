import random
import numpy as np
import pandas as pd
import random
import os
import time
import json

BASE_TEMPLATE = ['case_path', 'case_id', 'case_name', 'detection_time', 'reviewed']
SVDH_TEMPLATE = [
    'LorR',

    # ===== JSN =====
    'JSN_MCP_T', 'JSN_MCP_I', 'JSN_MCP_M', 'JSN_MCP_R', 'JSN_MCP_S',
    'JSN_PIP_I', 'JSN_PIP_M', 'JSN_PIP_R', 'JSN_PIP_S',
    'JSN_CMC_M', 'JSN_CMC_R', 'JSN_CMC_S',
    'JSN_S_TmTd', 'JSN_S_C', 'JSN_S_Ra',

    # ===== BE =====
    'BE_MCP_T', 'BE_MCP_I', 'BE_MCP_M', 'BE_MCP_R', 'BE_MCP_S',
    'BE_IP',
    'BE_PIP_I', 'BE_PIP_M', 'BE_PIP_R', 'BE_PIP_S',
    'BE_CMC_T',
    'BE_Tm', 'BE_S', 'BE_L', 'BE_Ul', 'BE_Ra'
]

class Scorer:
    def __init__(self, score_type='svdh'):
        self.datetime = time.time()
        self.tmp_info = []
        self.recent_idx = 0
        self.recent_path = ''

        if score_type == 'svdh':
            self.score_df = pd.DataFrame(columns=BASE_TEMPLATE + SVDH_TEMPLATE)
        else:
            self.score_df = None

    def update_score(self, case_path, LorR, *args):
        self.find_row(case_path, LorR)
        self.score_df.loc[self.recent_idx, self.score_df.columns[6:]] = list(args)


    def new_info(self, case_path, case_id, case_name, detection_time, LorR, *args):
        score_row = [case_path, case_id, case_name, detection_time, False, LorR] + list(args)
        self.score_df.loc[len(self.score_df)] = score_row
        self.recent_path = case_path
        self.recent_idx += 1

    def show(self):
        print(self.score_df.to_dict())

    # ---------- 保存 ----------
    def save(self, save_path):
        json_data = {
            'datetime': self.datetime,
            'recent_path': self.recent_path,
            'recent_idx': int(self.recent_idx),
            'score_df': self.score_df.to_dict(orient="records"),
        }

        with open(save_path, "w", encoding="utf-8") as f:
            json.dump(json_data, f, ensure_ascii=False, indent=4)

        print(f"Saved to {save_path}")

    def output(self, output_path):
        """
        将 score_df 和 review_df 导出到同一个 Excel 文件，两个 sheet
        """
        with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
            self.score_df.to_excel(writer, index=False, sheet_name='score')

        print(f"Excel saved to {output_path}")

    def find_row(self, case_path, LorR):
        df = self.score_df
        result = df[(df["case_path"] == case_path) & (df["LorR"] == LorR)]

        if result.empty:
            raise IndexError("Not find row")
        else:
            self.recent_idx = result.index[0]
            self.recent_path = case_path
        return result.to_dict(orient="records")

    def get_case_path_list(self):

        return self.score_df["case_path"].drop_duplicates().tolist()

    def reviewed(self):
        self.score_df.at[self.recent_idx, 'reviewed'] = True

    # ---------- 读取 ----------
    @classmethod
    def load(cls, json_path):
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        scorer = cls()
        scorer.datetime = data["datetime"]
        scorer.recent_path = data["recent_path"]
        scorer.score_df = pd.DataFrame(data["score_df"])
        return scorer


if __name__ == "__main__":
    scorer = Scorer()

    for i in range(5):
        scorer.set_base_info(
            case_path=f"/data/00{i}.png",
            case_id=f"00{i}",
            case_name=f"Patient_00{i}",
            detection_time="2025-01-01",
        )
        svdh_scores = [None for _ in range(31)]
        scorer.set_score_info('R', *svdh_scores)

        svdh_scores = [random.randint(0, 5) for _ in range(31)]
        scorer.set_score_info('R', *svdh_scores)

    # I/O
    scorer.save("demo_scores.json")
    scorer.output("demo_scores.xlsx")

    # function
    case_path_list = scorer.get_case_path_list()
    print(case_path_list)

    scorer.find_row('/data/002.png', 'R')
    scorer.update_score('BE_Ra', 100000)
    scorer.reviewed()

    scorer.show()

    # 测试读取
    new_scorer = Scorer.load("demo_scores.json")
    print("\nLoaded from JSON:")
    new_scorer.show()
