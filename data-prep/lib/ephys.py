# CREATED: 8-JUL-2025
# LAST EDIT: 8-JUL-2025
# AUTHOR: DUANE RINEHART, MBA (drinehart@ucsd.edu)

'''METHODS/FUNCTIONS FOR PROCESSING EPHYS EXPERIMENTAL MODALITY'''

import numpy as np
import h5py


def process_spike_data(ref_array, mat_file):
    all_clusters = []
    for i in range(len(ref_array)):
        ref = ref_array[i]
        if isinstance(ref, np.ndarray):
            if ref.size == 1:
                ref = ref.item()
            else:
                raise ValueError(f"Expected scalar ref at index {i}, but got array of shape {ref.shape}: {ref}")
        obj = mat_file[ref]
        print(f"Cluster {i}: keys = {list(obj.keys())}")

        # unwrap nested arrays to get scalar reference
        site_ref = obj["site"][0]
        if isinstance(site_ref, np.ndarray):
            site_ref = site_ref.item()
        site_obj = mat_file[site_ref]
        site_val = site_obj[()]
        site = int(site_val)

        quality_raw = obj["quality"][()]
        quality = quality_raw.decode() if isinstance(quality_raw, bytes) else quality_raw

        cluster_data = {
            "spike_times": np.array(obj["tm"]),
            "waveforms": np.array(obj["spkWavs"]),
            "trial_times": np.array(obj["trialtm"]),
            "trial_indices": np.array(obj["trial"]),
            "quality": quality,
            "site": site,
        }
        all_clusters.append(cluster_data)
    return all_clusters


def create_electrode_table(nwbfile, all_clusters, ephys_device):
    """Create electrode table from cluster data"""
    
    # Get all unique sites from clusters
    unique_sites = list({cluster['site'] for cluster in all_clusters})
    
    # Add each site to electrode table
    for site in unique_sites:
        nwbfile.add_electrode(
            id=site,
            x=0.0, y=0.0, z=0.0,  # Update with actual coordinates if available
            imp=np.nan,
            location=nwbfile.electrode_groups['1'].location,  # From meta group
            filtering='none',
            group=nwbfile.electrode_groups['1']  # From meta group
        )
    
    print(f"Added {len(unique_sites)} electrodes to table")


def create_electrical_series(nwbfile, all_clusters, sampling_rate=30000.0):
    """Create ElectricalSeries from spike data"""
    
    # Aggregate all spike data
    all_spike_times = []
    all_sites = []
    all_waveforms = []
    
    for cluster in all_clusters:
        # Convert samples to seconds
        spike_times = cluster['spike_times'] / sampling_rate
        all_spike_times.extend(spike_times)
        all_sites.extend([cluster['site']] * len(spike_times))
        
        # Collect waveforms
        if 'waveforms' in cluster:
            all_waveforms.append(cluster['waveforms'])
    
    # Create electrode table region
    electrode_region = nwbfile.create_electrode_table_region(
        region=all_sites,
        description='Electrodes with detected spikes',
        name='electrode_region'
    )
    
    # Create ElectricalSeries
    return ElectricalSeries(
        name='spike_waveforms',
        data=np.vstack(all_waveforms) if all_waveforms else None,
        electrodes=electrode_region,
        timestamps=np.array(all_spike_times),
        description='Sorted spike waveforms',
        comments=f'Contains {len(all_clusters)} sorted units',
        conversion=1.0,  # Update if needed
        resolution=np.nan,
        filtering='Bandpass 300-6000 Hz'  # Update with actual
    )