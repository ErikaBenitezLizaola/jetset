from __future__ import absolute_import, division, print_function

from builtins import (bytes, str, open, super, range,
                      zip, round, input, int, pow, object, map, zip)

__author__ = "Andrea Tramacere"


from .model_parameters import ModelParameterArray, ModelParameter
from .spectral_shapes import SED
from .data_loader import  ObsData
from .utils import  get_info
import numpy as np
import json
import pickle
import warnings
from .cosmo_tools import  Cosmo

__all__=['Model']




class Model(object):
    
    
    def __init__(self,name='no-name',nu_size=200,model_type='base_model',scale='lin-lin',cosmo=None):
        
        self.model_type=model_type
        
        self.name=name

        self.SED = SED(name=self.name)
    
        self.parameters = ModelParameterArray()    
        
        self._scale=scale
        
        self.nu_size=nu_size
        
        self.nu_min=None
        
        self.nu_max=None

        self.flux_plot_lim = 1E-30

        if cosmo is None:
          self.cosmo=Cosmo()

        self._set_version(v=None)
        
    @property
    def version(self):
        return self._version

    def _set_version(self, v=None):
        if v is None:
            self._version = get_info()['version']
        else:
            self._version = v

    def _prepare_nu_model(self,nu,loglog):

        if nu is None:
            x1 = np.log10(self.nu_min)
            x2 = np.log10(self.nu_max)
            lin_nu = np.logspace(x1, x2, self.nu_size)
            log_nu = np.log10(lin_nu)
        else:

            if np.shape(nu) == ():
                nu = np.array([nu])

            if loglog is True:
                lin_nu = np.power(10., nu)
                log_nu = nu
            else:
                log_nu = np.log10(nu)
                lin_nu = nu

        return lin_nu,log_nu

    def _eval_model(self,lin_nu,log_nu,loglog):
        log_model=None

        if loglog is False:
            lin_model = self.lin_func(lin_nu)
        else:
            if hasattr(self, 'log_func'):
                log_model = self.log_func(log_nu)
                lin_model = np.power(10., log_model)
            else:
                lin_model = self.lin_func(lin_nu)
                lin_model[lin_model<0.]=self.flux_plot_lim
                log_model = np.log10(lin_model)

        return lin_model,log_model

    def _fill(self, lin_nu, lin_model):

        if hasattr(self,'SED'):
            self.SED.fill(nu=lin_nu, nuFnu=lin_model)
            z=self.get_par_by_type('redshift')

            if z is not None:
                z=z.val

            if z is None and hasattr(self, 'get_redshift'):
                z=self.get_redshift()
                z = z

            #print('--> fill z ',self.name,self.name,z)
            if z is not None:
                if hasattr(self,'get_DL_cm'):
                    dl = self.get_DL_cm('redshift')
                else:
                    dl = self.cosmo.get_DL_cm(z)
                self.SED.fill_nuLnu( z =z, dl = dl)
        else:
            warnings.warn('model',self.name,'of type',type(self),'has no SED member')

        if hasattr(self, 'spectral_components_list'):
            for i in range(len(self.spectral_components_list)):
                self.spectral_components_list[i].fill_SED(lin_nu=lin_nu)

    def eval(self, fill_SED=True, nu=None, get_model=False, loglog=False, label=None, **kwargs):

        out_model = None
        #print('--> base model 1', nu[0])
        lin_nu,log_nu=self._prepare_nu_model(nu,loglog)
        #print('--> base model 2', lin_nu[0], log_nu[0],'loglog',loglog)
        lin_model,log_model  = self._eval_model(lin_nu,log_nu,loglog)

        if fill_SED is True:
            self._fill(lin_nu, lin_model)

        if get_model is True:

            if loglog is True:
                out_model = log_model
            else:
                out_model = lin_model

        return out_model


    def set_nu_grid(self,nu_min=None,nu_max=None,nu_size=None):
        if nu_size is not None:
            self.nu_size=nu_size
        
        if nu_min is not None:
            self.nu_min=nu_min
        
        if nu_max is not None:
            self.nu_max=nu_max


    def lin_func(self,lin_nu):
        return np.ones(lin_nu.size) * self.flux_plot_lim
    
    def log_func(self,log_nu):
        return np.log10(self.lin_func(np.power(10,log_nu)))



    def get_residuals(self, data, log_log=False,filter_UL=True):
        if isinstance(data,ObsData):
            data=data.data

        model = self.eval(nu=data['nu_data'], fill_SED=False, get_model=True, loglog=False)

        if filter_UL ==True:
            msk=data['UL']==False
        else:
            msk=np.ones(data.size,dt=True)

        residuals = (data['nuFnu_data'] - model) /  data['dnuFnu_data']

        nu_residuals=data['nu_data']


        if log_log == False:
            return nu_residuals[msk], residuals[msk]
        else:
            return  np.log10(nu_residuals[msk]),  residuals[msk]

    def save_model(self, file_name):

        pickle.dump(self, open(file_name, 'wb'), protocol=pickle.HIGHEST_PROTOCOL)


    @classmethod
    def load_model(cls, file_name):

        try:
            c = pickle.load(open(file_name, "rb"))
            if isinstance(c, Model):
                c.eval()
                return c
            else:
                raise RuntimeError('The model you loaded is not valid please check the file name')

        except Exception as e:
            raise RuntimeError(e)

    def show_model(self):
        print("")
        print("-------------------------------------------------------------------------------------------------------------------")

        print("model description")
        print(
            "-------------------------------------------------------------------------------------------------------------------")
        print("name: %s  " % (self.name))
        print("type: %s  " % (self.model_type))

        print('')

        self.show_pars()

        print("-------------------------------------------------------------------------------------------------------------------")

    def show_pars(self, sort_key='par type'):
        self.parameters.show_pars(sort_key=sort_key)

    def show_best_fit_pars(self):
        self.parameters.show_best_fit_pars()

    def set_par(self,par_name,val):
        """
        shortcut to :class:`ModelParametersArray.set` method
        set a parameter value

        :param par_name: (srt), name of the parameter
        :param val: parameter value

        """

        self.parameters.set(par_name, val=val)



    def get_par_by_type(self,par_type):
        """

        get parameter by type

        """
        for param in self.parameters.par_array:
            if param.par_type==par_type:
                return param

        return None

    def get_par_by_name(self,par_name):
        """

        get parameter by type

        """
        for param in self.parameters.par_array:
            if param.name==par_name:
                return param

        return None

class MultiplicativeModel(Model):

    def __init__(self, name='no-name', nu_size=100, model_type='multiplicative_model', scale='lin-lin'):
        super(MultiplicativeModel, self).__init__(name=name, nu_size=nu_size, model_type=model_type,scale=scale)
        delattr(self,'SED')

        #self.__call__ = self.eval
