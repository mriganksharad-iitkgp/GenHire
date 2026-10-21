import { useCallback, useEffect, useState } from 'react';
import { request } from 'shared/api/client';

export default function usePricingCatalog(enabled = true) {
  const [catalog,setCatalog]=useState(null),[error,setError]=useState('');
  const reload=useCallback(async()=>{setError('');try{const value=await request('/pricing/catalog',{auth:false,signalOn401:false});if(!value.credits||['practice_interview','practice_interview_proctored','candidate_invite','signup_bonus'].some(key=>!Number.isInteger(value.credits[key])||value.credits[key]<0))throw new Error('Current prices are unavailable. Retry before starting a paid action.');setCatalog(value);}catch(err){setCatalog(null);setError(err.message);}},[]);
  useEffect(()=>{if(enabled)reload();},[enabled,reload]);
  return {catalog,error,reload};
}
