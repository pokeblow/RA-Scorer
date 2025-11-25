import random
import numpy as np
import pandas as pd
import random
import os
import time
import json

SVDH_TEMPLATE = {
    'case_path': '',
    'case_id': 'null',
    'case_name': 'null',
    'reviewed': False,
    'LorR': '',

    'JSN': {
        'MCP-T': None, 'MCP-I': None, 'MCP-M': None, 'MCP-R': None, 'MCP-S': None,
        'PIP-I': None, 'PIP-M': None, 'PIP-R': None, 'PIP-S': None,
        'CMC-M': None, 'CMC-R': None, 'CMC-S': None,
        'STT': None, 'SC': None, 'SR': None
    },

    'BE': {
        'MCP-T': None, 'MCP-I': None, 'MCP-M': None, 'MCP-R': None, 'MCP-S': None,
        'IP': None, 'PIP-I': None, 'PIP-M': None, 'PIP-R': None, 'PIP-S': None,
        'CMC-T': None, 'Tm': None, 'S': None, 'L': None, 'U': None, 'R': None
    }
}


class Scorer:
    def __init__(self):
        self.datetime = time.time()
        self.tmp_info = []
        self.recent_idx = 0
        self.recent_path = ''

        self.score_repo = []  # 所有 case 的评分
        self.mapping = []
        self.index_map = {}   # (path, LorR) → index
        self.count_idx = 0

    def get_file_list(self):
        if len(self.score_repo) == 0:
            return None
        else:
            file_list = []
            for i in self.score_repo:
                if i['case_path'] not in file_list:
                    file_list.append(i['case_path'])

            return file_list

    def new_info(self, case_path, case_id, case_name, LorR, JSN_dict=None, BE_dict=None):
        # 深拷贝模板，避免各 case 数据互相污染
        score_dict = json.loads(json.dumps(SVDH_TEMPLATE))

        score_dict['case_path'] = case_path
        score_dict['case_id'] = case_id
        score_dict['case_name'] = case_name
        score_dict['LorR'] = LorR

        for key in score_dict['JSN'].keys():
            if JSN_dict == None:
                score_dict['JSN'][key] = None
            else:
                score_dict['JSN'][key] = JSN_dict.get(key)

        for key in score_dict['BE'].keys():
            if BE_dict == None:
                score_dict['BE'][key] = None
            else:
                score_dict['BE'][key] = BE_dict.get(key)

        self.index_map[(case_path, LorR)] = self.count_idx
        self.score_repo.append(score_dict)
        self.count_idx += 1

    def update_info(self, case_path, LorR, JSN_dict, BE_dict):
        idx = self.index_map.get((case_path, LorR), -1)
        score_dict = self.score_repo[idx]

        for key in score_dict['JSN'].keys():
            score_dict['JSN'][key] = JSN_dict.get(key)

        for key in score_dict['BE'].keys():
            score_dict['BE'][key] = BE_dict.get(key)

    def set_reviewed(self, case_path, state):
        idx = self.index_map.get((case_path, 'L'), -1)
        score_dict = self.score_repo[idx]
        score_dict['reviewed'] = state

        idx = self.index_map.get((case_path, 'R'), -1)
        score_dict = self.score_repo[idx]
        score_dict['reviewed'] = state

    def get_reviewed(self, case_path):
        idx = self.index_map.get((case_path, 'L'), -1)
        score_dict = self.score_repo[idx]
        return score_dict['reviewed']


    def get_info(self, case_path, LorR):
        idx = self.index_map.get((case_path, LorR), -1)
        score_dict = self.score_repo[idx]
        return score_dict['JSN'], score_dict['BE']

    # ====================================================
    #  保存当前状态到 JSON 文件
    # ====================================================
    def save_to_json(self, path):
        data = {
            "score_repo": self.score_repo,
            "count_idx": self.count_idx,
            "datetime": self.datetime,
        }

        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        print(f"[OK] 已保存到 {path}")


    # ====================================================
    #  从 JSON 读取并恢复状态
    # ====================================================
    def load_from_json(self, path):
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # 恢复基本内容
        self.score_repo = data.get("score_repo", [])
        self.count_idx = data.get("count_idx", len(self.score_repo))
        self.datetime = data.get("datetime", 0)

        # 自动重建 index_map
        self.index_map = {}
        for idx, item in enumerate(self.score_repo):
            key = (item["case_path"], item["LorR"])
            self.index_map[key] = idx

        print(f"[OK] 已从 {path} 恢复状态")

    def output_to_excel(self, path):
        rows = []

        for item in self.score_repo:
            base_info = {
                "case_path": item["case_path"],
                "case_id": item["case_id"],
                "case_name": item["case_name"],
                "reviewed": item["reviewed"],
                "LorR": item["LorR"],
            }

            # 展开 JSN
            jsn_info = {f"JSN_{k}": v for k, v in item["JSN"].items()}

            # 展开 BE
            be_info = {f"BE_{k}": v for k, v in item["BE"].items()}

            # 合并成一行
            row = {**base_info, **jsn_info, **be_info}
            rows.append(row)

        df = pd.DataFrame(rows)

        # 导出 Excel（一个 sheet）
        df.to_excel(path, index=False, sheet_name="Scores")

        print(f"[OK] 已成功导出到 Excel：{path}")


# ================================
#        ⭐ 测试代码 ⭐
# ================================
if __name__ == "__main__":
    scorer = Scorer()

    # -------- 新建 L / R 两个记录 --------
    for side in ['L', 'R']:
        JSN = {k: random.randint(0, 4) for k in SVDH_TEMPLATE['JSN'].keys()}
        BE = {k: random.randint(0, 4) for k in SVDH_TEMPLATE['BE'].keys()}

        scorer.new_info(
            case_path="/data/case001.png",
            case_id="001",
            case_name="case001",
            LorR=side,
            JSN_dict=JSN,
            BE_dict=BE
        )

    print("===== 初始评分 =====")
    for side in ['L', 'R']:
        jsn, be = scorer.get_info("/data/case001.png", side)
        print(f"{side} JSN:", jsn)
        print(f"{side} BE :", be)

    # -------- 更新 L 一次 --------
    JSN2 = {k: random.randint(0, 4) for k in SVDH_TEMPLATE['JSN'].keys()}
    BE2 = {k: random.randint(0, 4) for k in SVDH_TEMPLATE['BE'].keys()}

    scorer.update_info(
        case_path="/data/case001.png",   # 注意这里路径要与 new_info 一致
        LorR="L",
        JSN_dict=JSN2,
        BE_dict=BE2
    )

    print("\n===== 更新后评分 (L) =====")
    jsn, be = scorer.get_info("/data/case001.png", "L")
    print("L JSN:", jsn)
    print("L BE :", be)

    # -------- 保存到 JSON --------
    scorer.save_to_json("test.json")
    print("\n已保存到 test.json")

    # -------- 新建空 Scorer，加载 JSON --------
    scorer2 = Scorer()
    scorer2.load_from_json("test.json")

    print("\n===== 恢复后的信息 =====")
    for side in ['L', 'R']:
        jsn, be = scorer2.get_info("/data/case001.png", side)
        print(f"{side} JSN:", jsn)
        print(f"{side} BE :", be)

    print("\nindex_map:", scorer2.index_map)

    # -------- 导出 Excel --------
    scorer2.output_to_excel("scores.xlsx")
    print("\nExcel 已导出为 scores.xlsx")
