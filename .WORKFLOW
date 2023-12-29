notificationforwarder:
1) update version in
./notificationforwarder/bin/notificationforwarder:                      version=f'%(prog)%s 2.4')
./notificationforwarder/pyproject.toml:version = "2.4"
  to 2.4.0.1
 git commit
2) add tag which will become release
 git tag vn2.4.0.1
3) push commits and tags
 git push && git push --tags
 (--follow-tags only pushes annotated tags)
