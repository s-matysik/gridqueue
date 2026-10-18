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
2. downloads two consecutive editions of the disclosure directly from the publisher and prints the
   checksums;
3. recognizes the publisher **from the content of the document** and extracts the rows of the common
   schema;
4. evaluates the eight quality control rules;
5. computes the queue flows between the editions together with the **linkage precision** on the
   fields held out of the key;
6. compares the reproduced figures with those published in the paper and **aborts execution on a
   divergence**.

Point six is the counterpart of the assertions in the `reproducibility/` directory. A divergence need
not mean an error, the publisher may have replaced the edition, but it has to be visible rather than
passed over in silence.

## What the notebook does not do

It does not reproduce the extraction accuracy against the reference set, because that set requires a
human reading. It does not resolve coordinates, because the geometric gazetteer is a separate
download and is subject to ODbL, and the notebook should not quietly draw the user into licensing
duties. It also does not run the cross-sectional example on this publisher, because **it does not
meet the date coverage criterion** set before the result was computed; the notebook shows this
openly instead of computing a median on a dozen or so percent of the records.

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
