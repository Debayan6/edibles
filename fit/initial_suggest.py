import numpy as np

def initial_value(cw, continuum, damp_coef=None):

    # determine the range of variations for continuum
    min_continuum = continuum - 3
    max_continuum = continuum + 3

    # chech defining the damping coef
    if damp_coef is not None:
        damp_flag = 'defined'

    # determine the components of cloud
    if len(cw) == 1:
        fit_flag = 'astro_voigt'
    else:
        fit_flag = 'multi_trans'
        try:
            if len(cw[0]) >= 1:
                flag_comp = 'multi_cloud'
                Nd = len(cw)
        except TypeError:
            flag_comp = 'multi_cloud'#'single_cloud'
            cw_temp = []
            cw_temp.append(cw)
            cw = cw_temp
    # print flag_comp



    # voigt
    if fit_flag == 'astro_voigt':
        initial_value = np.array([continuum, 0.0, 0.0], dtype='double')
        for itr in range(len(cw)):
            initial_value = np.append(initial_value, 0.0)      # cloud velocity
            initial_value = np.append(initial_value, cw[itr])  # lambda0
            if damp_flag == 'defined':
                initial_value = np.append(initial_value, damp_coef[itr])
            else:
                initial_value = np.append(initial_value, 1.5e6)
            initial_value = np.append(initial_value, 2.0)      # doppler param
            initial_value = np.append(initial_value, 12.0)     # column density


    # multi transition
    if fit_flag == 'multi_trans':
        # single cloud
        if flag_comp == 'single_cloud':
            initial_value = np.array([continuum, 0.0, 0.0], dtype='double')
            for itr in range(len(cw)):
                initial_value = np.append(initial_value, 0.0)
                initial_value = np.append(initial_value, cw[itr])
            initial_value = np.append(initial_value, 2.0)
            initial_value = np.append(initial_value, 12.0)
        # multi cloud
        if flag_comp == 'multi_cloud':
            initial_value = np.array([continuum, 0.0, 0.0], dtype='double')
            for loop_t in range(len(cw)):
                sub_cw = cw[loop_t]
                for itr in range(len(sub_cw)):
                    initial_value = np.append(initial_value, sub_cw[itr])  # lambda0
                    if damp_flag == 'defined':
                        initial_value = np.append(initial_value, damp_coef[itr])
                    else: initial_value = np.append(initial_value, 1.5e6)
                initial_value = np.append(initial_value, 0.0)          # cloud velocity
                initial_value = np.append(initial_value, 2.0)          # doppler param
                initial_value = np.append(initial_value, 12.0)         # column density



    # -----------------------------------
    # Constraints for the initial values
    # -----------------------------------
    p0 = initial_value
    parinfo = [{'value':0., 'fixed':0, 'limited':[0,0], 'limits':[0.,0.]} for i in range(len(p0))]

    parinfo[0]['limited'][0] = 1
    parinfo[0]['limits'][0] = min_continuum
    parinfo[0]['limited'][1] = 1
    parinfo[0]['limits'][1] = max_continuum

    prc = 3
    for itr in range(len(cw)):

        # -------------
        # astro voigt -
        # -------------
        if fit_flag == 'astro_voigt':
            # CW
            parinfo[4+itr*5]['limited'][0] = 1
            parinfo[4+itr*5]['limits'][0] = cw[itr] - 0.2
            parinfo[4+itr*5]['limited'][1] = 1
            parinfo[4+itr*5]['limits'][1] = cw[itr] + 0.2
            # gamma
            if damp_flag == 'defined':
                parinfo[5+itr*5]['fixed'] = 1
            else:
                parinfo[5+itr*5]['limited'][0] = 1
                parinfo[5+itr*5]['limits'][0] = 0
            # b_eff
            parinfo[6+itr*5]['limited'][0] = 1
            parinfo[6+itr*5]['limits'][0] = 2
            parinfo[6+itr*5]['limited'][1] = 1
            parinfo[6+itr*5]['limits'][1] = 10
            # logN
            parinfo[7+itr*5]['limited'][0] = 1
            parinfo[7+itr*5]['limits'][0] = 7
            parinfo[7+itr*5]['limited'][1] = 1
            parinfo[7+itr*5]['limits'][1] = 24



        # -----------------
        # multi transition
        # -----------------
        if fit_flag == 'multi_trans' and flag_comp == 'multi_cloud':
            for loop_sub in range(len(cw[itr])):
                # CW
                parinfo[prc]['limited'][0] = 1
                parinfo[prc]['limits'][0] = cw[itr][loop_sub] - 0.2
                parinfo[prc]['limited'][1] = 1
                parinfo[prc]['limits'][1] = cw[itr][loop_sub] + 0.2
                prc += 1
                # gamma
                if damp_flag == 'defined':
                    parinfo[prc]['fixed'] = 1
                else:
                    parinfo[prc]['limited'][0] = 1
                    parinfo[prc]['limits'][0] = 0
                prc += 1

            # v_cloud
            parinfo[prc]['limited'][0] = 1
            parinfo[prc]['limits'][0] = -1000
            parinfo[prc]['limited'][1] = 1
            parinfo[prc]['limits'][1] = 1000
            prc += 1
            # b_eff
            parinfo[prc]['limited'][0] = 1
            parinfo[prc]['limits'][0] = 2
            parinfo[prc]['limited'][1] = 1
            parinfo[prc]['limits'][1] = 10
            prc += 1
            # log_N
            parinfo[prc]['limited'][0] = 1
            parinfo[prc]['limits'][0] = 7
            parinfo[prc]['limited'][1] = 1
            parinfo[prc]['limits'][1] = 24
            prc += 1



        # -----------------
        # multi transition
        # -----------------
        if fit_flag == 'multi_trans' and flag_comp == 'single_cloud':
            # CW
            parinfo[2+itr*4]['limited'][0] = 1
            parinfo[2+itr*4]['limits'][0] = cw[itr] - 0.2
            parinfo[2+itr*4]['limited'][1] = 1
            parinfo[2+itr*4]['limits'][1] = cw[itr] + 0.2

            # b_eff
            parinfo[-2]['limited'][0] = 1
            parinfo[-2]['limits'][0] = 2
            parinfo[-2]['limited'][1] = 1
            parinfo[-2]['limits'][1] = 10
            # logN
            parinfo[-1]['limited'][0] = 1
            parinfo[-1]['limits'][0] = 7
            parinfo[-1]['limited'][1] = 1
            parinfo[-1]['limits'][1] = 24

    # fill out the dictionary
    for itr in range(len(p0)): parinfo[itr]['value'] = p0[itr]

    return parinfo, p0