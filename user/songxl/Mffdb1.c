/* 1-D Fourier finite-difference wave extrapolation */
/*
  Copyright (C) 2008 University of Texas at Austin
  
  This program is free software; you can redistribute it and/or modify
  it under the terms of the GNU General Public License as published by
  the Free Software Foundation; either version 2 of the License, or
  (at your option) any later version.
  
  This program is distributed in the hope that it will be useful,
  but WITHOUT ANY WARRANTY; without even the implied warranty of
  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
  GNU General Public License for more details.
  
  You should have received a copy of the GNU General Public License
  along with this program; if not, write to the Free Software
  Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
*/
#include <rsf.h>
#include "vconstant.h"
#include "abcpass.h"

int main(int argc, char* argv[]) 
{
    int nx, nt, nk, ik, ix, it, nft, nb, nxb, abc, v0kind;
    float dt, dx, dk, k;
    float *old, *nxt, *cur, *sig, *v, *nxttmp, 
    v0, **aa, tv, tv0, dv, pi=SF_PI, tmpk, 
    *w, *dercur, *derold;
    sf_file in, out, vel;
    bool opt,pad;    /* optimal padding */
    sf_complex  *uk, *uktmp; 
    kiss_fftr_cfg cfg, cfgi;

    sf_init(argc,argv);
    in  = sf_input("in");
    vel = sf_input("vel");   /* velocity */
    out = sf_output("out");

    if (SF_FLOAT != sf_gettype(in)) sf_error("Need float input");
    if (SF_FLOAT != sf_gettype(vel)) sf_error("Need float input");
    if (!sf_histint(vel,"n1",&nx)) sf_error("No n1= in input");
    if (!sf_histfloat(vel,"d1",&dx)) sf_error("No d1= in input");
    if (!sf_getbool("opt",&opt)) opt=true;
    if (!sf_getbool("try",&pad)) pad=false;
    if (!sf_getfloat("dt",&dt)) sf_error("Need dt input");
    if (!sf_getint("nt",&nt)) sf_error("Need nt input");
    if (!sf_getint("nb",&nb)) nb =20; 
    if (!sf_getint("v0",&v0kind)) v0kind = 0; 
    if (!sf_getint("abc",&abc)) abc =0; /*absorbing boundary condition 1: cos 0: exp*/ 

    sf_putint(out,"n1",nx);
    sf_putfloat(out,"d1",dx);
//    sf_putfloat(out,"o1",x0);
    sf_putint(out,"n2",nt);
    sf_putfloat(out,"d2",dt);
    sf_putfloat(out,"o2",0.0); 

    nxb=nx+2*nb;

    nft = opt? 2*kiss_fft_next_fast_size((nxb+1)/2): nxb;
    if (nft%2) nft++;
    nk = nft/2+1;
    dk = 1./(nft*dx);

    sig = sf_floatalloc(nx);
    old = sf_floatalloc(nxb);
    nxt = sf_floatalloc(nxb);
    nxttmp = sf_floatalloc(nxb);
    cur = sf_floatalloc(nxb);
    dercur = sf_floatalloc(nxb);
    derold = sf_floatalloc(nxb);
    v = sf_floatalloc(nxb);
    aa = sf_floatalloc2(2,nxb);
    uk = sf_complexalloc(nk);
    uktmp = sf_complexalloc(nk);

    w = sf_floatalloc(nb);
   /* sb = 4.0*nb;
    for(ib=0; ib<nb; ib++){
       fb = ib/(sqrt(2.0)*sb);
       w[ib] = exp(-fb*fb);
    }*/
    abc_cal(abc,nb, 0.0001,w);
/*    switch(abc){
          case(1): 
              for(ib=0; ib<nb; ib++){
                 w[ib]=(1.0+0.9*cosf(((float)(nb-1.0)-(float)ib)/(float)(nb-1.0)*pi))/2.0;
              }
          break;
          case(0): 
              for(ib=0; ib<nb; ib++){
                 w[ib]=exp(-0.0001*(nb-1-ib)*(nb-1-ib));
              }
          break;
          default:
              for(ib=0; ib<nb; ib++){
                 //w[ib]=powf(cosf(pi/2.0*ib/(nb-1.0)),abc);
                 w[ib]=powf((1.0+0.9*cosf(((float)(nb-1.0)-(float)ib)/(float)(nb-1.0)*pi))/2.0,abc);
              }
          break;
    }  */ 
    sf_floatread(v,nx,vel);
    sf_floatread(sig,nx,in);		
    sf_floatwrite(sig,nx,out);

    for (ix= nb+nx-1; ix > nb-1; ix--) {
        v[ix] = v[ix-nb];
         } 
    
    for (ix=0; ix < nb; ix++){
        v[ix] = v[nb];
        v[ix+nb+nx] = v[nx+nb-1];
        }

    v0=v0_cal(v,nxb,v0kind);
    tv0 = v0*v0*dt*dt;

    for (ix=0; ix < nxb; ix++){
        tv = dt*dt*v[ix]*v[ix];
        dv = (v[ix]*v[ix]-v0*v0)*dt*dt/(dx*dx);
        aa[ix][0] = tv*(1.0 - dv/6.0);
        aa[ix][1] = tv*dv/12.0;
    } 
       /* for (ix=0; ix < nb; ix++){
            aa[ix][0] *= (1.0+cosf(((float)(nb-1.0)-(float)ix)/(float)(nb-1)*pi))/2.0;
            aa[ix+nb+nx][1] *= (1.0+cosf((float)ix/(float)(nb-1)*pi))/2.0;
        }*/
	/* initial conditions */
    for (ix=0; ix < nx; ix++){
        cur[ix+nb] =  sig[ix];
    }
    for (ix=0; ix < nb; ix++){
        cur[ix] = cur[nb];
        cur[ix+nb+nx] = cur[nx+nb-1];
        }
    for (ix=0; ix < nxb; ix++){
        old[ix] =  0.0; 
	nxt[ix] = 0.;
        derold[ix] = cur[ix]/dt ;
    }

    free(v);
    free(sig);

    cfg = kiss_fftr_alloc(nft,0,NULL,NULL); 
    cfgi = kiss_fftr_alloc(nft,1,NULL,NULL); 
    /* propagation in time */
    for (it=1; it < nt; it++) {
        for (ix=0; ix < nb; ix++){
       //     cur[ix] *= w1[ix] ;
        //   cur[ix+nb+nx] *= w1[nb-1-ix];
        } 
	kiss_fftr(cfg,cur,(kiss_fft_cpx*)uk);/*compute  u(k) */
#ifdef SF_HAS_COMPLEX_H
        for (ik=0; ik < nk; ik++) {
            k =  ik * dk*2.0*pi;
            tmpk = v0*fabs(k)*dt;
            uktmp[ik] = uk[ik]*2.0*(cosf(tmpk)-1.0)/tv0;
         }

#else
         for (ik=0; ik < nk; ik++) {
             k =  ik * dk*2.0*pi;
             tmpk = v0*fabs(k)*dt;
             uktmp[ik] = sf_crmul(uk[ik],2.0*(cosf(tmpk)-1.0)/tv0);
         }
#endif
	 kiss_fftri(cfgi,(kiss_fft_cpx*)uktmp,nxttmp);

	for (ix=0; ix < nxb; ix++) nxttmp[ix] /= (float)nft; 
 /*       for (ix=0; ix < nb; ix++){
            nxttmp[ix] *= w1[ix]; 
            nxttmp[ix+nb+nx] *= w1[nb-1-ix];
            cur[ix] *= w1[ix] ;
            cur[ix+nb+nx] *= w1[nb-1-ix];
            old[ix] *= w1[ix]; 
            old[ix+nb+nx] *= w1[nb-1-ix];
        } */

	/* Stencil */
//	nxt[0] = nxttmp[0]*aa[0][0] + nxttmp[0]*aa[0][0] + nxttmp[1]*aa[0][1];
	nxt[0] = nxttmp[0]*aa[0][0] +  nxttmp[1]*aa[0][1];
	for (ix=1; ix < nxb-1; ix++) {
	    nxt[ix] = nxttmp[ix]*aa[ix][0] + nxttmp[ix+1]*aa[ix][1] + nxttmp[ix-1]*aa[ix][1];
	}
//	nxt[nxb-1] = nxttmp[nxb-1]*aa[nxb-1][1] + nxttmp[nxb-1]*aa[nxb-1][0] + nxttmp[nxb-2]*aa[nxb-1][1];
	nxt[nxb-1] = nxttmp[nxb-1]*aa[nxb-1][0] + nxttmp[nxb-2]*aa[nxb-1][1];
	
	for (ix=0; ix < nxb; ix++){
            dercur[ix]= derold[ix] + nxt[ix]/dt;
            } 
	for (ix=0; ix < nxb; ix++) {
	    nxt[ix] =  cur[ix] + dercur[ix]*dt;
	}
        for (ix=0; ix < nb; ix++){
            nxt[ix] *= w[ix];
            nxt[ix+nb+nx] *= w[nb-1-ix];
            dercur[ix] *= w[ix];
            dercur[ix+nb+nx] *= w[nb-1-ix];
        }
	sf_floatwrite(nxt+nb,nx,out);
	for (ix=0; ix < nxb; ix++) {
	    old[ix] = cur[ix];
	    cur[ix] = nxt[ix];
	    derold[ix] = dercur[ix];
	}
    }

    sf_fileclose(vel);
    sf_fileclose(in);
    sf_fileclose(out);
    exit(0);
}
