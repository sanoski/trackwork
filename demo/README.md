# Demo data

A fictional railroad so a fresh install has something to look at: the Northern Valley
Railroad's North Division (a company line with two worksites, three weeks of ties, three
switches, a derail, and some downtime) and Project 1187 (a finished sponsored job that beat
its goal). Every name and number is made up.

Seed it during install with `deploy/setup.sh --demo`, or later with
`scripts/cli.py import demo/data --overwrite`. No accounts are included; setup always asks
you to create the real first admin.

The dates are anchored to the week before the dataset was generated. To refresh them, run
`python demo/make_demo.py` from the repository root; it rebuilds `demo/data` through the
app's own service layer so the files are always valid.
