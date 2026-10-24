---
title: Google Colab
---

# Running in the browser

[![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/s-matysik/gridqueue/blob/main/notebooks/gridqueue_colab.ipynb)

The notebook `notebooks/gridqueue_colab.ipynb` removes the installation barrier: a reviewer or an
analyst at the regulator runs the full workflow without installing anything, without an account and
without an accelerator.

## What the notebook does

1. installs the package from a **tagged release**, not from the main branch, so the result does not
   depend on the current state of the repository;
2. downloads two consecutive editions of the transmission operator's disclosure directly from the
   publisher and prints the checksums;
3. recognizes the publisher **from the content of the document**, extracts the rows of the common
   schema and validates them;
4. evaluates the eight quality control rules and the column-shift audit;
5. computes the queue flows between the editions together with the **linkage precision** on the
   fields held out of the key and the **key sensitivity**;
6. compares the reproduced figures with those published in the paper and **aborts execution on a
   divergence**;
7. downloads ENERGA-OPERATOR's three documents of one edition and reproduces the processing-time
   strata (Kaplan-Meier with censoring) and the node loading of the paper, with the same check;
8. runs the location resolver on a synthetic gazetteer, draws every chart and packs the results into
   one archive.

Points six and seven are the counterpart of the assertions in the `reproducibility/` directory. A
divergence need not mean an error, the publisher may have replaced the edition, but it has to be
visible rather than passed over in silence. Point seven parses PDF documents and adds several
minutes; it can be switched off with `RUN_ENERGA = False`.

## What the notebook does not do

It does not reproduce the extraction accuracy against the reference set, because that set requires a
human reading. It does not use the national geometric gazetteer, which is a separate download subject
to ODbL; the resolver is shown on a synthetic gazetteer, and one line points it at your own. It does
not compute processing times for the transmission operator, because that publisher **does not meet
the date coverage criterion** set before the result was computed; the notebook shows this openly
instead of computing a median on a dozen or so percent of the records.

## When a download fails

Two situations are anticipated and both end with a message rather than an exception.

**Code 404.** Editions move in time, and older ones are sometimes removed once they are replaced.
Download the current list from the publisher's site, upload it through the file panel and enter the
name in the `pliki` dictionary.

**Certificate verification error.** Typical in corporate and institutional networks with an
intermediary server that substitutes the certificate chain; it does not occur in Colab. The notebook
**does not circumvent that control** and directs the user to upload the file manually.

## Where the notebook stands relative to CI

Continuous integration **does not run** the notebook, because it reaches for documents that are
replaced quarterly, and a job that depends on an external publication would break for reasons
unrelated to the code. A separate job does check what can be checked without network access: whether
all the code cells are syntactically correct and whether every name imported from the package really
exists in it. It is precisely that second check which answers the defect revealed by the first run of
the notebook: the documentation promised an `as_frame` method that the package did not have.
