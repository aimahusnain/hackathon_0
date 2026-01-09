# AI Employee Dashboard

> Real-time summary of bank balance, pending messages, and active business projects.

**Last Updated:** {{date:YYYY-MM-DD HH:mm}}

---

## Quick Stats

| Metric          | Value                                     |
| --------------- | ----------------------------------------- |
| Pending Emails  | ![[Needs_Action]] count matching `EMAIL_` |
| Pending Files   | ![[Needs_Action]] count matching `FILE_`  |
| Tasks Today     | 0                                         |
| Tasks Completed | 0                                         |

---

## Priority Action Items

### 🔴 Urgent (Needs Immediate Attention)
```dataview
TABLE priority, type, received
FROM "Needs_Action"
WHERE priority = "high" OR status = "pending"
SORT received DESC
LIMIT 5
```

### 🟡 Needs Response
```dataview
TABLE type, subject
FROM "Needs_Action"
WHERE status = "pending"
SORT received DESC
LIMIT 10
```

---

## Recent Activity

### Inbox Processing
```dataview
TABLE file.ctime
FROM "Inbox"
SORT file.ctime DESC
LIMIT 5
```

### Completed Items
```dataview
TABLE completed_date
FROM "Done"
SORT completed_date DESC
LIMIT 5
```

---

## Financial Overview

### Bank Balance
- **Current Balance:** $0.00
- **Last Updated:** N/A

### Pending Payments
```dataview
TABLE vendor, amount, due_date
FROM "Needs_Action"
WHERE type = "payment"
SORT due_date ASC
```

---

## Projects Overview

```dataview
TABLE status, due_date
FROM "Plans"
WHERE status = "active"
SORT due_date ASC
```

---

## Quick Links

- [[Company_Handbook]] - Rules and procedures
- [[Needs_Action]] - Items requiring attention
- [[Inbox]] - New incoming items
- [[Done]] - Completed tasks
- [[Plans]] - Active projects
- [[Logs]] - Activity logs

---

## System Status

| Watcher | Status | Last Check |
|---------|--------|------------|
| Gmail Watcher | 🟢 Running | {{date:YYYY-MM-DD HH:mm}} |
| File System Watcher | 🟢 Running | {{date:YYYY-MM-DD HH:mm}} |
| WhatsApp Watcher | ⚪ Not Configured | N/A |

---

## Daily Summary

### Tasks Completed Today
- [ ] Task 1
- [ ] Task 2
- [ ] Task 3

### Notes
- Add important notes here
- Track patterns or recurring issues
