---
title: Limitations
---

# Limitations

We state them together with the figures, not only in a separate section, because without them part
of the results would be used incorrectly.

## What the register is not

* **It is not an estimate of the available connection capacity.** It discloses the **queue, not the
  reserve**. The available capacity field belongs to the node entity from point 2 of the duty and is
  populated only where the publisher discharges that point with a capacity figure.
* **It is not a representation of the state of the network.** It describes administrative
  proceedings, some of which will never reach completion. The settlement of a process is a legal
  event, not a physical one.
* **It is not a ranking of locations.** It contains no model of preferences.
* **It is not an index of publications.** There are tools that index operators' pages at European
  scale; this package goes one layer lower and parses the document itself.

## Incommensurability of disclosures under the same provision

Two publishers discharge the same point of the duty in forms that cannot be compared: one reports
**available capacity**, the other **a count of free connection slots**. We mapped the latter onto a
constraint flag and an extension field, leaving the capacity field empty; entering a count of slots
into a capacity field would be fabricating a unit. This is an empirical finding, not an
implementation inconvenience.

## Extent of coverage

Six publishers at row level against approximately 180 licensed distribution system operators in
Poland. Four of them belong to the six covered by the agreed reporting template, which marks out a
verifiable horizon for extension, but **does not license any claim about the distribution of formats
among the remaining publishers**.

## Access to the sources

* **One large operator remains unavailable, and not because of a certificate.** The missing
  intermediate certificate was obtained from the AIA pointer in the server certificate, and once it
  had been added the service answers with code 200 under full verification. The blocker is
  **server-side client filtering**: to an honest identifying header the service returns a rejection
  page. Reproducing a browser fingerprint would circumvent a control the operator put in place
  deliberately, so we did not attempt it.
* Two foreign portals return 403 at row level. We use only their public metadata and describe it as
  such. **We do not circumvent access controls**; the client identifies itself honestly in the
  identifying header.

## Accuracy measurement

* The reference set is **partly single-annotator**: inter-annotator agreement was measured on a
  subsample of 35 rows, whereas the reference sets of two publishers remain single-annotator.
* The sample is **clustered**, runs of consecutive rows on randomly chosen pages rather than a simple
  random sample, so the effective precision is lower than the same number of independent draws would
  give.
* The reference set covers the **application entity**; the accuracy of the node tables, including the
  available capacity field and the five-year horizons, was not measured separately.
* The percentage share from the first measurement run **must not be cited as a point of reference**
  for the final value, because the set of measured fields changed; what is comparable is the
  breakdown per field.

## Location

* The location at the largest publisher is an **internal substation code**; the operator does not
  publish a dictionary of the codes, so the resolver returns missing-with-reason. **It does not
  guess.** Obtaining the substation code dictionaries would in a single step turn this register from
  an aspatial one into a spatial one.
* A street name does not determine a point, see [validation](walidacja.md).

## Transferability

Six row-level sources in two jurisdictions are a **demonstration of transferability, not a proof of
generality**. The foreign adapter works on data that is **already tabular**, so transferability was
shown on a case easier than the Polish one; a second jurisdiction publishing documents meant for
printing would be stronger proof.

## Licence

To be settled. The licences of the input data are separate and fixed: the OpenStreetMap gazetteer
under ODbL; the operators' statutory publications under their own terms of use, redistributed only
where that is permitted.
