/* -*- c++ -*- ----------------------------------------------------------
   LAMMPS - Large-scale Atomic/Molecular Massively Parallel Simulator
   http://lammps.sandia.gov, Sandia National Laboratories
   Steve Plimpton, sjplimp@sandia.gov

   Copyright (2003) Sandia Corporation.  Under the terms of Contract
   DE-AC04-94AL85000 with Sandia Corporation, the U.S. Government retains
   certain rights in this software.  This software is distributed under
   the GNU General Public License.

   See the README file in the top-level LAMMPS directory.
------------------------------------------------------------------------- */

#ifndef LMP_IMBALANCE_H
#define LMP_IMBALANCE_H

#include <stdio.h>

namespace LAMMPS_NS {
 class LAMMPS;

class Imbalance {
 public:
  Imbalance(LAMMPS *lmp) : _lmp(lmp) {};
  virtual ~Imbalance() {};

  // disallow default and copy constructor, assignment operator
 private:
  Imbalance() {};
  Imbalance(const Imbalance &) {};
  Imbalance &operator=(const Imbalance &) {return *this;};

  // internal use only data members
 protected:
  LAMMPS *_lmp;

  // public API
 public:
  // parse options. return number of arguments consumed. (required)
  virtual int options(int narg, char **arg) = 0;
  // reinitialize internal data (needed for fix balance) (optional)
  virtual void init() {};
  // compute and apply weight factors to local atom array (required)
  virtual void compute(double *weights) = 0;
  // print information about the state of this imbalance compute (required)
  virtual void info(FILE *fp) = 0;
};

}

#endif
