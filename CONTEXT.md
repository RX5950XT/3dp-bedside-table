# 目前狀態

最新版 v3。250 mm 沿床板、200 mm 跨床板，平臺厚 4、夾壁厚 5、夾深 90、夾槽 28.9 mm。
依使用者要求：四片三角支撐，內外各兩片，左右端各一片；厚 4、向下最多 50 mm，不能做成與夾壁同深。
平臺四角 R8、上下緣 R1、夾片與支撐外緣 R0.6。
單一一體成形，無螺絲、彈片或組裝零件。木板 28.7 mm、可夾深 120 mm，目標置物 1.5 kg。
工作檔 models/BedsideShelf.FCStd；最新版 STL/STEP 在 exports/current、切片檔在 manufacturing/current。舊版保留於 archive 子目錄。
FreeCAD 單一實體、木板零干涉、STL 回讀及四視角通過；A1 4 圈牆、預設 15% gyroid、無支撐切片成功且無警告，估 341.6 g / 11 小時 18 分。
實印鬆緊、承重與蠕變未驗證。規格與重建方式見 README.md、source/build_shelf.py。
