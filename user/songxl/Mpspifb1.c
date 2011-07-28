/* 1-D finite-difference wave extrapolation */
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
#include <math.h>
#include <limits.h>
#ifdef _OPENMP
#include <omp.h>
#endif
#include "abcpass.h" 
int main(int argc, char* argv[]) 
{
    int nx, nt, nk, nft, ix, it, ik, iv, nv, nb, nxb, abc;
    float dt, dx, dk, k, dv, tmpdt, pi=SF_PI, vmax, vmin, wsum;
    float *sig,  *nxt,  *old, *cur, *nxtc, *w, *dercur, *derold;
    sf_complex  *uk,*uktmp; 
    kiss_fftr_cfg cfg,cfgi;
   // float  *v, *vx, *weight; 
    float  *v, *vc, **weight; 
    sf_file inp, out, vel;
    bool opt;    /* optimal padding */
   // #ifdef _OPENMP
   // int nth;
   // #endif
     

    sf_init(argc,argv);
    inp = sf_input("in");
    out = sf_output("out");
    vel = sf_input("vel");   /* velocity */
  //  grad = sf_input("grad"); /* velocity gradient */

    if (SF_FLOAT != sf_gettype(inp)) sf_error("Need float input");
    if (SF_FLOAT != sf_gettype(vel)) sf_error("Need float input");
    if (!sf_histint(vel,"n1",&nx)) sf_error("No n1= in input");
    if (!sf_histfloat(vel,"d1",&dx)) sf_error("No d1= in input");
  //  if (!sf_histint(inp,"n2",&nt)) sf_error("No n2= in input");
  //  if (!sf_histfloat(inp,"d2",&dt)) sf_error("No d2= in input");
    if (!sf_getbool("opt",&opt)) opt=true;
    if (!sf_getfloat("dt",&dt)) sf_error("Need dt input");
    if (!sf_getint("nt",&nt)) sf_error("Need nt input");
    if (!sf_getint("nv",&nv)) sf_error("Need nv input");
    if (!sf_getint("nb",&nb)) nb =20; 
    if (!sf_getint("abc",&abc)) abc =0; /*absorbing boundary condition 1: cos 0: exp*/ 
    /* if y, determine optimal size for efficiency */

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

    uk = sf_complexalloc(nk);
    uktmp = sf_complexalloc(nk);

 //   nv =4;
    sig    =  sf_floatalloc(nx);
    old    =  sf_floatalloc(nxb);
    cur    =  sf_floatalloc(nxb);
    nxt    =  sf_floatalloc(nxb);
    nxtc   =  sf_floatalloc(nxb);
    vc     =  sf_floatalloc(nv);
    weight =  sf_floatalloc2(nxb,nv);
    dercur = sf_floatalloc(nxb);
    derold = sf_floatalloc(nxb);
/* pass ABC */
    w = sf_floatalloc(nb);
    abc_cal(abc,nb,0.0001,w);
    
    v = sf_floatalloc(nxb);
 //   vx = sf_floatalloc(nx);

    sf_floatread(v,nx,vel);
    for (ix= nb+nx-1; ix > nb-1; ix--) {
        v[ix] = v[ix-nb];
         } 
    
    for (ix=0; ix < nb; ix++){
        v[ix] = v[nb];
        v[ix+nb+nx] = v[nx+nb-1];
        }
//    sf_floatread(vx,nx,grad);
    vmax = -FLT_MAX;
    vmin = +FLT_MAX;
    for (ix=0; ix < nxb; ix++) {
        if (v[ix] > vmax) vmax = v[ix];
        if (v[ix] < vmin) vmin = v[ix];
        }
    dv = (vmax-vmin)/(nv-1);
    for (iv=0; iv < nv; iv++) vc[iv] = vmin + dv * iv;
    for (ix=0; ix < nxb; ix++) {
         wsum = 0.0;
         for (iv=0; iv < nv; iv++) {
             weight[iv][ix] = 1.0/((v[ix]-vc[iv])*(v[ix]-vc[iv])/10000.0+1.0); // Weight Function
             wsum += weight[iv][ix];
            }
         for (iv=0; iv < nv; iv++) weight[iv][ix] /= wsum;
        }
    cfg = kiss_fftr_alloc(nft,0,NULL,NULL); 
    cfgi = kiss_fftr_alloc(nft,1,NULL,NULL); 

    sf_floatread(sig,nx,inp);		
    sf_floatwrite(sig,nx,out);

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

    free(sig);
/*
    #ifdef _OPENMP
    #pragma omp parallel
   {nth = omp_get_num_threads();}
    sf_warning("using %d threads",nth);
    #endif
*/
    /* propagation in time */
    for (it=1; it < nt; it++) {

        for (ix=0; ix < nxb; ix++) nxt[ix] = 0.0; 

	kiss_fftr(cfg,cur,(kiss_fft_cpx*)uk);/*compute  u(k) */

/*    #ifdef _OPENMP
    #pragma omp parallel for private(ik,ix,x,k,tmp,tmpex,tmpdt) 
    #endif
*/
        for (iv=0; iv < nv; iv++){
#ifdef SF_HAS_COMPLEX_H
              for (ik=0; ik < nk; ik++) {
                  k =  ik * dk*2.0*pi;
                  tmpdt = vc[iv]*fabs(k)*dt;
                  uktmp[ik] = uk[ik] *2.0*(cosf(tmpdt)-1)/(vc[iv]*vc[iv]*dt*dt);
                  }

#else
              for (ik=0; ik < nk; ik++) {
                  k =  ik * dk*2.0*pi;
                  tmpdt = vc[iv]*fabs(k)*dt;
                  uktmp[ik] = sf_crmul(uk[ik],2.0*(cosf(tmpdt)-1)/(vc[iv]*vc[iv]*dt*dt));
                  }
#endif
	      kiss_fftri(cfgi,(kiss_fft_cpx*)uktmp,nxtc);/*compute  u(k) */
	      for (ix=0; ix < nxb; ix++) {  
                   nxtc[ix] /= nft; 
		  // nxtc[ix] -= old[ix];
		   nxtc[ix] *= weight[iv][ix];
                   nxt[ix] += nxtc[ix];
                   }
               }  
        for(ix=0; ix < nxb; ix++){
                nxt[ix] *= (v[ix]*v[ix]*dt);
              } 
	for (ix=0; ix < nxb; ix++){
            dercur[ix]= derold[ix] + nxt[ix];
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

   /*free(nxt);     
   free(nxtc);     
   free(cur);     
   free(old);     
   free(uk);     
   free(v);     
   free(uktmp);  */   
sf_fileclose(vel);
sf_fileclose(inp);
sf_fileclose(out);
 
   exit(0); 
}           
           
