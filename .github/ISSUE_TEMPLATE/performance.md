---
name: Performance issue
about: Report performance problems or suggest optimizations
title: '[PERFORMANCE] '
labels: ['performance']
assignees: ''

---

## Performance Issue Description
Describe the performance problem you're experiencing.

## Environment
- OS: [e.g. macOS 12.0, Ubuntu 20.04, Windows 10]
- Python version: [e.g. 3.9.0]
- TaskPanel version: [e.g. 1.0.1]
- Terminal: [e.g. iTerm2, Terminal.app, Windows Terminal]
- Hardware: [e.g. CPU, RAM, SSD/HDD]

## Task Configuration
- Number of tasks: [e.g. 50]
- Number of steps per task: [e.g. 5]
- Task duration: [e.g. each step takes ~30 seconds]
- Worker limit: [e.g. 10]

## Performance Metrics
What specific performance issues are you seeing?
- [ ] High CPU usage
- [ ] High memory usage
- [ ] Slow UI responsiveness
- [ ] Slow task execution
- [ ] Long startup time
- [ ] Other: ___________

## Measurements
If you have specific measurements, please include them:
- CPU usage: [e.g. 80% constant]
- Memory usage: [e.g. 2GB RAM]
- Response time: [e.g. 5 seconds delay]
- Task completion time: [e.g. 2x slower than expected]

## Steps to Reproduce
1. Configure TaskPanel with [specific configuration]
2. Run `taskpanel tasks.csv`
3. Observe [specific performance issue]

## Expected Performance
What performance would you expect?

## Profiling Data
If you have profiling data, please attach it or paste relevant sections:
```
Profiling output here
```

## System Resource Usage
Please provide output from system monitoring tools if available:
```
htop, top, Activity Monitor, or Task Manager output
```

## Additional Context
- Does this happen with all task configurations or only specific ones?
- Have you tried different worker limits?
- Are there any workarounds you've found?

## Checklist
- [ ] I have verified this isn't a configuration issue
- [ ] I have tested with different task configurations
- [ ] I have provided relevant system information
- [ ] I have described the expected vs actual performance
