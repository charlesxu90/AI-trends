# Conference Sources

Source links for every tracked conference-year. This is the human-maintained index
the pipeline ingests from: each row's URL feeds `ai-trend ingest-url <URL>`
(OpenReview venue or `openaccess.thecvf.com`). Extend it monthly — add new
conference-years as they post, and re-check existing links.

- **OpenReview** column: ICLR / ICML / NeurIPS (api2 venue groups).
- **Other source** column: CVPR / ICCV via CVF open-access (`thecvf.com`), or
  secondary links.
- **Date**: accepted-papers availability / conference date (MM/DD/YYYY).

| Year | Conf | Date | OpenReview | Other source |
|------|------|------|------------|--------------|
| 2026 | ACL | 7/2/2026 | | https://aclanthology.org/events/acl-2026/ |
| 2026 | ICLR | 4/23/2026 | https://openreview.net/group?id=ICLR.cc/2026/Conference | |
| 2026 | CVPR | 6/10/2026 | | https://openaccess.thecvf.com/CVPR2026?day=all |
| 2025 | ICCV | 10/19/2025 | | https://openaccess.thecvf.com/ICCV2025?day=all |
| 2025 | NIPS | 12/10/2025 | https://openreview.net/group?id=NeurIPS.cc/2025/Conference#tab-accept-oral | |
| 2025 | ICML | 7/27/2025 | https://openreview.net/group?id=ICML.cc/2025/Conference#tab-accept-oral | |
| 2025 | CVPR | 6/17/2025 | | https://openaccess.thecvf.com/CVPR2025?day=all |
| 2025 | ICLR | 5/7/2025 | https://openreview.net/group?id=ICLR.cc%2F2025%2FConference | |
| 2024 | NIPS | 12/10/2024 | https://openreview.net/group?id=NeurIPS.cc/2024/Conference#tab-accept-oral | |
| 2024 | ICML | 7/27/2024 | https://openreview.net/group?id=ICML.cc/2024/Conference#tab-accept-oral | https://icml.cc/ |
| 2024 | CVPR | 6/17/2024 | | https://openaccess.thecvf.com/CVPR2024?day=all |
| 2024 | ICLR | 5/7/2024 | https://openreview.net/group?id=ICLR.cc/2024/Conference#tab-accept-oral | |
| 2023 | NIPS | 12/10/2023 | https://openreview.net/group?id=NeurIPS.cc/2023/Conference | |
| 2023 | ICCV | 10/1/2023 | | https://openaccess.thecvf.com/ICCV2023?day=all |
| 2023 | ICML | 7/23/2023 | https://openreview.net/group?id=ICML.cc/2023/Conference | https://openreview.net/group?id=ICML.cc/2023/Workshop/ILHF |
| 2023 | CVPR | 6/18/2023 | | https://openaccess.thecvf.com/CVPR2023?day=all |
| 2023 | ICLR | 5/1/2023 | https://openreview.net/group?id=ICLR.cc/2023/Conference | |
| 2022 | NIPS | 11/28/2022 | https://openreview.net/group?id=NeurIPS.cc/2022/Conference | |
| 2022 | ICML | 7/17/2022 | https://openreview.net/group?id=ICML.cc/2022/Workshop | |
| 2022 | CVPR | 6/19/2022 | | https://openaccess.thecvf.com/CVPR2022?day=all |
| 2022 | ICLR | 4/25/2022 | https://openreview.net/group?id=ICLR.cc/2022/Conference#oral-submissions | |
| 2021 | NIPS | 12/6/2021 | https://openreview.net/group?id=NeurIPS.cc/2021/Conference#oral-presentations | |
| 2021 | ICML | 7/18/2021 | https://openreview.net/group?id=ICML.cc/2021/Workshop | |
| 2021 | CVPR | 6/19/2021 | | https://openaccess.thecvf.com/CVPR2021?day=all |
| 2021 | ICLR | 5/3/2021 | https://openreview.net/group?id=ICLR.cc/2021/Conference | |

<!--
Maintenance (monthly):
  - Add a new row when a tracked conference posts accepted papers (set Date + URL).
  - Re-check existing links are still live (see `ai-trend check-sources`, planned).
  - To ingest a row: `ai-trend ingest-url "<OpenReview or Other-source URL>"`.
  - New venues also need an entry in config/conferences.json (key/label/tokens/month/source).
-->
