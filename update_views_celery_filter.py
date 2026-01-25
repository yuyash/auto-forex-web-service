#!/usr/bin/env python3
"""Update views to filter by celery_task_id."""

# Read the file
with open("backend/apps/trading/views/task.py", "r") as f:
    lines = f.readlines()

# Find and update logs endpoints
for i, line in enumerate(lines):
    # Update logs endpoint - replace task_service call with direct query
    if i < len(lines) - 5 and "logs = self.task_service.get_task_logs(" in line:
        # Find the end of this method call
        j = i
        while j < len(lines) and "return Response" not in lines[j]:
            j += 1

        # Replace the block
        indent = "            "
        new_block = [
            f"{indent}# Filter by current execution (celery_task_id)\n",
            f"{indent}logs_queryset = TaskLog.objects.filter(\n",
            f"{indent}    task=task,\n",
            f"{indent}    celery_task_id=task.celery_task_id,\n",
            f"{indent})\n",
            f"{indent}\n",
            f"{indent}if level:\n",
            f"{indent}    logs_queryset = logs_queryset.filter(level=level)\n",
            f"{indent}\n",
            f'{indent}logs = logs_queryset.order_by("-timestamp")[offset : offset + limit]\n',
            f"{indent}serializer = TaskLogSerializer(logs, many=True)\n",
        ]
        lines[i:j] = new_block

    # Update trades endpoint - add celery_task_id filter
    if "ExecutionTrade.objects.filter(task=task).order_by" in line:
        lines[i] = line.replace(
            "ExecutionTrade.objects.filter(task=task)",
            "ExecutionTrade.objects.filter(\n                task=task,\n                celery_task_id=task.celery_task_id,\n            )",
        )

    # Update equity endpoint - add celery_task_id filter
    if (
        "ExecutionEquity.objects.filter(task=task)" in line and "order_by" in lines[i + 1]
        if i + 1 < len(lines)
        else False
    ):
        lines[i] = line.replace(
            "ExecutionEquity.objects.filter(task=task)",
            "ExecutionEquity.objects.filter(\n                    task=task,\n                    celery_task_id=task.celery_task_id,\n                )",
        )

# Write back
with open("backend/apps/trading/views/task.py", "w") as f:
    f.writelines(lines)

print("✅ Updated views to filter by celery_task_id")
