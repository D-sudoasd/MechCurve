# Local agent workflow · 本地 Agent 工作流

Install the optional agent dependencies with `python -m pip install -e ".[agent]"`. A host with shell access can use the CLI directly. A host with MCP stdio support can launch the installed `mechcurve-mcp` executable. Substitute the absolute path to your virtual environment if the host does not inherit its PATH.

```json
{
  "mcpServers": {
    "mechcurve": {
      "command": "mechcurve-mcp",
      "args": []
    }
  }
}
```

| Tool | Task |
| --- | --- |
| `list_protocols()` | List supported methods and coordinate pairs. |
| `inspect_directory(input_dir, notes)` | List relative acquisition IDs and associated metadata. |
| `analyze_directory(input_dir, output_dir, notes, lang)` | Read the source directory and create a versioned offline delivery. Supply the notes as a JSON object. Language defaults to `zh`. |
| `read_cycles(run, record, cycle)` | Read a segment or a specific specimen-global cycle. |
| `review_rows(run, record, row, radius)` | Return original observations around a selected physical source row. |
| `verify_delivery(run)` | Recheck artifact hashes and provide paths, counts and parsing failures. |

### A reproducible agent task

> Inspect the demo folder and analyze it in English with the supplied notes. Verify the delivery. For Resumed B, return the two 1.3% target visits with acquisition ID, cycle number, unload stress, residual strain and source row. Link the specimen sheet and identify which measured cycle determines the maximum fully recoverable strain.

The host reads `examples/demo/notes.json` and passes its contents to `analyze_directory`. Capture `run` from the tool response. Query cycle 3 in `resumed-b1.csv` and cycle 4 in `resumed-b2.csv`. For each observation, corroborate `end_row` with `review_rows`. Results distinguish measured facts, the configured recovery criterion and any interpretation supplied in a note.

### Delivery and reuse

Open the returned `entry` for the most recently verified run in that language. `run.json` holds input and artifact SHA-256 hashes, package runtime versions, font identities, PDF page counts and stage timings. `results.json` holds the event tables and per-specimen fits. The receipt's `stage_metrics` describes the build that created that run. Reopening an identical verified run returns its existing receipt. Changing a sheet layout can reuse both the numerical analysis and independent figure assets. Failed or partial records appear in `failed_records`. The CLI returns exit code 2 for a partial delivery.

### 中文操作顺序

先用 `inspect_directory` 获取原始记录 ID。将样品身份、续测顺序和已知断裂信息写入备注，调用 `analyze_directory`。在返回的 `run` 下，使用 `read_cycles` 和 `review_rows` 核对关键周次、换向点与卸载端点，再用 `verify_delivery` 检查交付，向实验者提供样品单页、批次报告和逐周表。补充解释应列出对应采集文件和原始行号。

### Mixed protocols and single acquisitions

Pass a file or directory via the existing input argument. Inspect the detected physical channels and classification basis, then analyze with any specimen, geometry or window notes. A visible Excel worksheet has its own record ID. Use that exact ID when examining a reported source row. For a fatigue waveform, `read_cycles` accepts an acquisition-local peak-to-peak excursion number. For other protocol metrics, call `read_cycles` with the record ID alone and read the returned `curve.metrics`. Each metric carries its unit and source rows. [Protocol reference](protocols.md)
